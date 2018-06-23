import logging
from sqlalchemy import create_engine, and_, desc
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound

from database.db_models import DB_Drug, DB_Source, DB_Hit, Base


class DB:
    def __init__(self, db_name="drugs.db"):
        self.engine = create_engine('sqlite:///'+db_name, echo=False)
        self.session_factory = sessionmaker(bind=self.engine)
        self.logger = logging.getLogger('__main__')
        pass

    def create_session(self):
        self.logger.debug("Creating session")
        session = scoped_session(self.session_factory)
        return session()

    def create_database(self):
        self.logger.debug("Creating database")
        Base.metadata.create_all(self.engine)

    def add_item(self, item, session):
        session.add(item)

    def delete_item(self,item, session):
        session.delete(item)

    def query_all(self, item, session):
        return session.query(item).all()

    def save_changes(self,session):
        session.commit()

    def close_db(self):
        self.engine.dispose()

class Drugs_DB(DB):

    def __init__(self, db_name="drugs.db"):
        DB.__init__(self, db_name)
        pass

    def get_drug(self, session, db_id=None, name=None):
        try:
            if name:
                return session.query(DB_Drug).filter(DB_Drug.name == name).one()
            elif db_id:
                return session.query(DB_Drug).filter(DB_Drug.id == db_id).one()
            else:
                return None
        except NoResultFound:
            return None

    def get_source(self, session, db_id=None, name=None):
        try:
            if name:
                return session.query(DB_Source).filter(DB_Source.name == name).one()
            elif db_id:
                return session.query(DB_Source).filter(DB_Source.id == db_id).one()
            else:
                return None
        except NoResultFound:
            return None

    def get_distinct_drug_hits(self, session):
        try:
            r = session.query(DB_Hit.drug_id).distinct().all()
            return [item[0] for item in r]
        except NoResultFound:
            return None

    def get_sources_ids_for_drug(self, session, drug_id):

        r = session.query(DB_Hit.source_id).filter(DB_Hit.drug_id == drug_id).distinct().all()
        return [item[0] for item in r]  # returns [] on empty

    def get_sources_names_for_drug(self, session, drug_id):

        r = session.query(DB_Hit).filter(DB_Hit.drug_id == drug_id).group_by(DB_Hit.source_id).all()
        return [item.source.name for item in r]  # returns [] on empty

    def get_hits_for_drug_and_source(self, session, drug_id, source_id):
        try:
            if drug_id is None and source_id is None:
                return None
            elif drug_id is None:
                condition = and_(DB_Hit.source_id == source_id)
            elif source_id is None:
                condition = and_(DB_Hit.drug_id == drug_id)
            else:
                condition = and_(DB_Hit.drug_id == drug_id, DB_Hit.source_id == source_id)

            hits = session.query(DB_Hit).filter(condition).order_by(desc(DB_Hit.hit_ts)).all()

            return hits
        except NoResultFound:
            return []

    def get_hit_stats_for_drug_and_source(self, session, drug_id, source_id):
        try:
            samesrc_samedrug_hits = len(self.get_hits_for_drug_and_source(session, drug_id, source_id))
            diffsrcs_samedrug_hits = len(self.get_hits_for_drug_and_source(session, drug_id, None))
            return samesrc_samedrug_hits, diffsrcs_samedrug_hits
        except NoResultFound:
            return None

    def optimize_hits_table(self, session):
        all_hits = self.get_distinct_drug_hits(session)
        for drug_id in all_hits:
            sources = self.get_sources_ids_for_drug(session, drug_id)
            for src in sources:
                ds_hits = self.get_hits_for_drug_and_source(session, drug_id, src)
                for idx, hit in enumerate(ds_hits):
                    if idx != 0 and idx < len(ds_hits) - 1:
                        self.delete_item(hit, session)

    def add_drugs_if_not_in_db(self, pp_drugs, session):
        drugs = dict()
        for drug_name in pp_drugs:
            result = self.get_drug(session, name=drug_name)
            if result is None:
                new_drug = DB_Drug(drug_name)
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
            result = self.get_source(session, name=source.name)
            if result is None:
                new_source = DB_Source(source.name, source.url, source.display_name, source.twitter_name, scan_ts,
                                       scan_ts)
                self.add_item(new_source, session)
                result = self.get_source(session, name=source.name)
            else:
                result.updated_ts = scan_ts
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

if __name__ == "__main__":
    pass

