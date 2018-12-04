import argparse
import os
import sys
import logging.handlers
from shutil import copy2

from database.lawsuit_database import DbHit
from database.lawsuit_database import DrugsDb
from drug_sources.web_scraping_sources import *
from twitter.twitter import LawsuitsTwitter, DuplicateTweet, TwitterLockedForSpam


class DrugAlert:

    def __init__(self):
        self.twitter = None
        self.db = None
        self.session = None

    def initalize_twitter(self):
        """
        Initlizes twitter and logs in
        :return: None
        """
        twitter_auth = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), 'twitter_auth.json')
        self.twitter = LawsuitsTwitter(twitter_auth)

    def send_tweets(self, hits, live=False):
        """
        Prepares tweets and (if in live mode) sends them to Twitter
        :param hits: dictionary containing hit information
        :param live: If true, tweets will be posted
        :return: errors, if any
        """
        tweets = self.twitter.prepare_tweets(hits)
        error = None
        for tweet in tweets:
            logger.info(tweet)
            if live:
                try:
                    self.twitter.post_tweet(tweet)
                    time.sleep(0.5)
                except DuplicateTweet:
                    logger.warning('Tweet already posted!')
                except TwitterLockedForSpam:
                    logger.error('Too many tweets resulted in spam')
                    error = 'Twitter locked the account'
        return error

    def send_dm_if_error(self, errors):
        """
        Sends DM via Twitter to admin
        :param errors: table of messages to send
        :return: None
        """
        for err in errors:
            if err is not None:
                self.twitter.admin_fix_me_dm(err)
                time.sleep(1)

    def initialize_db(self, live=False):
        """
        Initializes database. Non-live mode will copy current database and use it for test.
        :param live: If true, will use main database
        :return: None
        """
        if not live:
            test_run_db = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), 'test.db')
            drugs_db = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), 'drugs.db')
            try:
                os.remove(test_run_db)
            except FileNotFoundError:
                pass
            try:
                copy2(drugs_db, test_run_db)
            except FileNotFoundError:
                logger.error('Cannot find database file drugs.db')
                raise RuntimeError
            self.db = DrugsDb(test_run_db)
            self.db.create_database()
        else:
            self.db = DrugsDb()

        self.session = self.db.create_session()

    @staticmethod
    def postprocess_scans(all_scans):
        """
        Changes scan dictionary structure for easier processing of scans
        :param all_scans: array of dictionaries with drug hits, [{'drugs':{'drug_name':'drug_url'},
                                                                            'source':source_object
                                                                            'ts':scan_timestamp}]
        :returns dictionary of results {'drugs':['drug_name'],
                                        'hits':[('drug_name',source_object,scan_timestamp)]
                                        'sources':[(source_object,scan_timestamp)]}
        """
        objects = {'drugs': set(),
                   'hits': [],
                   'sources': []
                   }
        for scan in all_scans:
            objects['sources'].append((scan['source'], scan['ts']))
            for drug in scan['drugs']:
                objects['drugs'].add(drug)
                objects['hits'].append((drug, scan['source'], scan['ts'], scan['drugs'][drug]))
        return objects

    def process_drugs_from_scan(self, drugs):
        """
        Adds drugs to database
        :param drugs: names of drugs
        :return: dictionary of drugs with their database IDs
        """
        self.db.add_drugs_if_not_in_db(drugs, self.session)
        return self.db.get_drug_ids(drugs, self.session)

    def process_sources_from_scan(self, sources):
        """
        Adds sources to database
        :param sources: names of sources
        :return: dictionary of sources with their database IDs
        """
        self.db.add_sources_if_not_in_db(sources, self.session)
        return self.db.get_sources_ids(sources, self.session)

    def evaluate_postprocessed_scans(self, postprocessed_scans):
        """
        Evaluates hits. First it's checking if all scanned drugs and sources are in the database.
        Then it's adding new hits to database
        :param postprocessed_scans: dictionary of results in following format:
                                        {'drugs':['drug_name'],
                                        'hits':[('drug_name',source_object,scan_timestamp)]
                                        'sources':[(source_object,scan_timestamp)]}
        :return: dictionary of drugs with information if drug was just discovered
                    {'drug_name': {'first_hit':bool_value,
                                    'new_sources':[source_object],
                                    'old_sources':[source_object]}}
        """
        new_hits = dict()

        drugs = self.process_drugs_from_scan(postprocessed_scans['drugs'])
        sources = self.process_sources_from_scan(postprocessed_scans['sources'])

        for drug, source, scan_ts, desc in postprocessed_scans['hits']:

            same_src_hits_for_drug, total_drug_hits = self.db.get_hit_stats_for_drug_and_source(self.session,
                                                                                                drugs[drug],
                                                                                                sources[source.name])
            current_src_names_for_drug = self.db.get_sources_names_for_drug(self.session, drugs[drug])
            current_srcs_for_drug = [getattr(sys.modules[__name__], item) for item in current_src_names_for_drug]

            DrugAlert.process_new_hit(new_hits, drug, source, same_src_hits_for_drug, total_drug_hits,
                                      current_srcs_for_drug)
            new_hit = DbHit(drugs[drug], sources[source.name], scan_ts)
            self.db.add_item(new_hit, self.session)

        return new_hits

    @staticmethod
    def process_new_hit(drugs_with_new_hits, drug, source, same_src_hits_for_drug, total_drug_hits, old_srcs):
        """
        Processes drugs with new hits, evaluates new and old sources
        :param drugs_with_new_hits: dictionary of drugs that are not in the database
        :param drug: drug name
        :param source: source object
        :param same_src_hits_for_drug: number of drug hits for source
        :param total_drug_hits: total hits of one drug (from all sources)
        :param old_srcs: sources that had drug hit in the past
        """
        if drug not in drugs_with_new_hits:
            drugs_with_new_hits[drug] = dict()
            if total_drug_hits == 0:
                drugs_with_new_hits[drug]['first_hit'] = True
            else:
                drugs_with_new_hits[drug]['first_hit'] = False

            if same_src_hits_for_drug == 0:
                drugs_with_new_hits[drug]['new_sources'] = [source]
                drugs_with_new_hits[drug]['old_sources'] = old_srcs
            else:
                drugs_with_new_hits[drug]['new_sources'] = []
                drugs_with_new_hits[drug]['old_sources'] = old_srcs
        else:
            if same_src_hits_for_drug == 0:
                drugs_with_new_hits[drug]['new_sources'].append(source)

    def run(self, live, from_file):
        """
        Main task that scans drug sources, evaluates them, saves results to database and publishes to twitter
        :param live: True saves results to database and publishes on Twitter
        :param from_file: True reads data from files instead of urls,
        does not publish on twitter regardless of live setting
        """
        self.initialize_db(live)
        self.initalize_twitter()
        srcs = get_all_scraping_sources()
        scans = []
        errors = []

        for src_class in srcs.values():
            source = src_class()
            try:
                scans.append(source.get_drugs(from_file=from_file))
            except NoDrugsFound:
                logger.error('No drugs found in scraping source {}'.format(source.url))
                errors.append('No drugs found in scraping source {}'.format(source.url))

        pp_scans = self.postprocess_scans(scans)
        new_hits = self.evaluate_postprocessed_scans(pp_scans)
        self.db.optimize_hits_table(self.session)

        errors.append(self.send_tweets(new_hits, live=live))

        self.db.save_changes(self.session)
        if live and not from_file:
            self.send_dm_if_error(errors)
        logger.info("Finished!")


def set_logger(level, size_megabytes=10, file_count=5):
    levels = {
        'DEBUG': logging.DEBUG,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR
    }
    lgr = logging.getLogger('__main__')
    try:
        lgr.setLevel(levels[level])
    except KeyError:
        lgr.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(module)s]- %(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    lgr.addHandler(console_handler)
    path_to_script = os.path.dirname(os.path.realpath(sys.argv[0]))
    output_file = os.path.join(path_to_script, 'log.log')
    file_handler = logging.handlers.RotatingFileHandler(
        output_file, maxBytes=(size_megabytes * 1024 * 1024), backupCount=file_count)
    file_handler.setFormatter(formatter)
    lgr.addHandler(file_handler)
    return lgr


def setup_arg_parser():
    prsr = argparse.ArgumentParser(description='todo')

    prsr.add_argument("-mode",  help="Live mode saves results to database and publishes on Twitter",
                      choices=["LIVE", "TEST_LIVE", "TEST_FILE", "UPDATE_TEST_FILES"], required=True)

    prsr.add_argument("-debug", help="Debug level", default='INFO', choices=['INFO', 'WARNING', 'CRITICAL', 'DEBUG'])
    return prsr


logger = None

if __name__ == "__main__":
    parser = setup_arg_parser()
    args = parser.parse_args()

    logger = set_logger(args.debug)

    DA = DrugAlert()

    if args.mode == "LIVE":
        DA.run(live=True, from_file=False)
    elif args.mode == "TEST_LIVE":
        DA.run(live=False, from_file=False)
    elif args.mode == "TEST_FILE":
        DA.run(live=False, from_file=True)
    elif args.mode == 'UPDATE_TEST_FILES':
        update_test_sources()
