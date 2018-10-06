import argparse
import logging.handlers
from shutil import copy2

from database.lawsuit_database import DB_Hit
from database.lawsuit_database import Drugs_DB
from drug_sources.web_scraping_sources import *
from twitter.twitter import LawsuitsTwitter


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
    objects = dict()
    objects['drugs'] = []
    objects['hits'] = []
    objects['sources'] = []
    for scan in all_scans:
        scan_ts = scan['ts']
        src = scan['source']
        objects['sources'].append((src, scan_ts))
        for drug in scan['drugs']:
            objects['drugs'].append(drug)
            objects['hits'].append((drug, src, scan_ts, scan['drugs'][drug]))
    objects['drugs'] = list(set(objects['drugs']))
    return objects


def evaluate_postprocessed_scans(db, session, postprocessed_scans):
    """
    Evaluates hits. First it's checking if all scanned drugs and sources are in the database. 
    Then it's adding new hits to database
    :param db: Database object
    :param session: Session object
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

    db.add_drugs_if_not_in_db(postprocessed_scans['drugs'], session)
    drugs = db.get_drug_ids(postprocessed_scans['drugs'], session)
    db.add_sources_if_not_in_db(postprocessed_scans['sources'], session)
    sources = db.get_sources_ids(postprocessed_scans['sources'], session)

    for drug, source, scan_ts, desc in postprocessed_scans['hits']:

        same_src_hits_for_drug, total_drug_hits = db.get_hit_stats_for_drug_and_source(session,
                                                                                       drugs[drug],
                                                                                       sources[source.name])
        current_src_names_for_drug = db.get_sources_names_for_drug(session, drugs[drug])
        current_srcs_for_drug = [getattr(sys.modules[__name__], item) for item in current_src_names_for_drug]

        process_new_hit(new_hits, drug, source, same_src_hits_for_drug, total_drug_hits, current_srcs_for_drug)
        new_hit = DB_Hit(drugs[drug], sources[source.name], scan_ts)
        db.add_item(new_hit, session)

    return new_hits


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


def run(live, from_file):
    """
    
    :param live: True saves results to database and publishes on Twitter 
    :param from_file: True reads data from files instead of urls, does not publish on twitter regardless of live setting
    """
    error = None
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
        db = Drugs_DB(test_run_db)
        db.create_database()
    else:
        db = Drugs_DB()
    twitter_auth = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), 'twitter_auth.json')
    twitter = LawsuitsTwitter(twitter_auth)
    session = db.create_session()
    srcs = get_all_scraping_sources()
    scans = []

    for src_class in srcs.values():
        try:
            scans.append(src_class().get_drugs(from_file=from_file))
        except NoDrugsFound:
            logger.error('No drugs found in scraping source {}'.format(src_class._url))
            error = 'No drugs found in scraping source {}'.format(src_class.url)

    pp_scans = postprocess_scans(scans)
    new_hits = evaluate_postprocessed_scans(db, session, pp_scans)
    db.optimize_hits_table(session)

    tweets = twitter.prepare_tweets(new_hits)

    for tweet in tweets:
        logger.info(tweet)
        if live:
            twitter.post_tweet(tweet)
            time.sleep(0.5)
    db.save_changes(session)
    logger.info("Success!")

    if live and not from_file and (error is not None):
        twitter.admin_fix_me_dm(error)


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

    if args.mode == "LIVE":
        run(live=True, from_file=False)
    elif args.mode == "TEST_LIVE":
        run(live=False, from_file=False)
    elif args.mode == "TEST_FILE":
        run(live=False, from_file=True)
    elif args.mode == 'UPDATE_TEST_FILES':
        update_test_sources()
