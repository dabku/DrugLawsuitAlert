import logging
from sqlalchemy import create_engine, and_, desc
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound
from os import path
import sys

from database.db_models import DbDrug, DbSource, DbHit, Base

logger = logging.getLogger(__name__)


class DB:
    def __init__(self, db_name="drugs.db", db_path=None):
        if not db_path:
            full_path = 'sqlite:///' + path.join(path.dirname(path.realpath(sys.argv[0])), db_name)
        else:
            full_path = 'sqlite:///'+path.join(db_path, db_name)
        self.engine = create_engine(full_path, echo=False)
        self.session_factory = sessionmaker(bind=self.engine)

    def create_session(self):
        logger.debug("Creating session")
        session = scoped_session(self.session_factory)
        return session()

    def create_database(self):
        logger.debug("Creating database")
        Base.metadata.create_all(self.engine)

    @staticmethod
    def add_item(item, session):
        session.add(item)

    @staticmethod
    def delete_item(item, session):
        session.delete(item)

    @staticmethod
    def query_all(item, session):
        return session.query(item).all()

    @staticmethod
    def save_changes(session):
        session.commit()

    def close_db(self):
        self.engine.dispose()


class DrugsDb(DB):
    def __init__(self, db_name="drugs.db", db_path=None):
        DB.__init__(self, db_name, db_path)

    @staticmethod
    def get_drug(session, db_id=None, name=None):
        try:
            if name:
                return session.query(DbDrug).filter(DbDrug.name == name).one()
            elif db_id:
                return session.query(DbDrug).filter(DbDrug.id == db_id).one()
        except NoResultFound as e:
            logger.debug('Drug not found for id={} name={}'.format(db_id, name))
            raise e

    @staticmethod
    def get_source(session, db_id=None, name=None):
        try:
            if name:
                return session.query(DbSource).filter(DbSource.name == name).one()
            elif db_id:
                return session.query(DbSource).filter(DbSource.id == db_id).one()
        except NoResultFound as e:
            logger.debug('Source not found for id={} name={}'.format(db_id, name))
            raise e

    @staticmethod
    def get_distinct_drug_hits(session):
        try:
            return [item[0] for item in session.query(DbHit.drug_id).distinct().all()]
        except NoResultFound as e:
            logger.debug('No hits found')
            raise e

    @staticmethod
    def get_sources_ids_for_drug(session, drug_id):
        sources_from_hits_query = session.query(DbHit.source_id)
        sources_from_hits_for_drug = sources_from_hits_query.filter(DbHit.drug_id == drug_id).distinct().all()
        return [item[0] for item in sources_from_hits_for_drug]

    @staticmethod
    def get_sources_names_for_drug(session, drug_id):
        hits_query = session.query(DbHit)
        hit_sources_for_drug = hits_query.filter(DbHit.drug_id == drug_id).group_by(DbHit.source_id).all()
        return [item.source.name for item in hit_sources_for_drug]

    @staticmethod
    def get_hits_for_drug_and_source(session, drug_id, source_id):
        if drug_id is None and source_id is None:
            raise NoResultFound
        elif drug_id is None:
            condition = and_(DbHit.source_id == source_id)
        elif source_id is None:
            condition = and_(DbHit.drug_id == drug_id)
        else:
            condition = and_(DbHit.drug_id == drug_id, DbHit.source_id == source_id)
        hits = session.query(DbHit).filter(condition).order_by(desc(DbHit.hit_ts)).all()
        if not hits:
            logger.debug('Source not found for id={} name={}'.format(drug_id, source_id))
            raise NoResultFound
        return hits

    def get_hit_stats_for_drug_and_source(self, session, drug_id, source_id):
        try:
            try:
                samesrc_samedrug_hits = len(self.get_hits_for_drug_and_source(session, drug_id, source_id))
            except NoResultFound:
                samesrc_samedrug_hits = 0
            try:
                diffsrcs_samedrug_hits = len(self.get_hits_for_drug_and_source(session, drug_id, None))
            except NoResultFound:
                diffsrcs_samedrug_hits = 0
            return samesrc_samedrug_hits, diffsrcs_samedrug_hits
        except NoResultFound:
            logger.debug('Hit not found for drug_id={} source_id={}'.format(drug_id, source_id))
            raise NoResultFound

    def optimize_hits_table(self, session):
        try:
            all_hits = self.get_distinct_drug_hits(session)
        except NoResultFound:
            logger.debug('No hits found in the database. Hit optimization not needed.')
            return
        for drug_id in all_hits:
            try:
                sources = self.get_sources_ids_for_drug(session, drug_id)
            except NoResultFound:
                raise RuntimeError('Hits were found in the database, but no sources are available')
            for src in sources:
                try:
                    ds_hits = self.get_hits_for_drug_and_source(session, drug_id, src)
                except NoResultFound:
                    raise RuntimeError('Hit was not found for drug and source.')
                for idx, hit in enumerate(ds_hits):
                    if idx != 0 and idx < len(ds_hits) - 1:
                        self.delete_item(hit, session)

    def add_drugs_if_not_in_db(self, pp_drugs, session):
        drugs = dict()
        for drug_name in pp_drugs:
            try:
                result = self.get_drug(session, name=drug_name)
            except NoResultFound:
                new_drug = DbDrug(drug_name)
                self.add_item(new_drug, session)
                result = self.get_drug(session, None, drug_name)
            drugs[drug_name] = result.id
        return drugs

    def get_drug_ids(self, drugs_noids, session):
        drugs = dict()
        for drug_name in drugs_noids:
            result = self.get_drug(session, name=drug_name)
            if result is None:
                raise NoResultFound
            drugs[drug_name] = result.id
        return drugs

    def add_sources_if_not_in_db(self, pp_sources, session):
        sources = dict()
        for source, scan_ts in pp_sources:
            try:
                result = self.get_source(session, name=source.name)
                result.updated_ts = scan_ts
            except NoResultFound:
                new_source = DbSource(source.name, source.url, source.display_name, source.twitter_name, scan_ts,
                                      scan_ts)
                self.add_item(new_source, session)
                result = self.get_source(session, name=source.name)
            sources[source.name] = result.id
        return sources

    def get_sources_ids(self, sources_noids, session):
        sources = dict()
        for source, scan_ts in sources_noids:
            result = self.get_source(session, name=source.name)
            if result is None:
                raise NoResultFound
            sources[source.name] = result.id
        return sources
