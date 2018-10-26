from TwitterAPI import TwitterAPI
import json
import random
import logging
# https://github.com/geduldig/TwitterAPI/blob/master/examples


class TweetNotSent(Exception):
    pass


class TwitterError(Exception):
    pass

class DuplicateTweet(Exception):
    pass


class Twitter:
    url_length = 23

    def __init__(self, config_json_file):
        with open(config_json_file) as json_data_file:
            config_json = json.load(json_data_file)
        self.api = TwitterAPI(config_json["consumer_key"],
                              config_json["consumer_secret"],
                              config_json["token_key"],
                              config_json["token_secret"])
        self.logger = logging.getLogger('__main__')
        self.admin_profile = config_json["admin_profile"]

    def post_tweet(self, text):
        self.logger.info("Posting tweet: {}".format(text))
        r = self.api.request('statuses/update', {'status': text})
        if r.status_code != 200:
            self.logger.error("Posting tweet failed with code {}".format(r.status_code))
            self.logger.error("Response content {}".format(r.response.content))
            try:
                code_error = json.loads(r.response.content)['errors'][0]['code']
            except KeyError:
                self.logger.error
                raise TweetNotSent
            if code_error == 187:
                self.logger.error('Status is a duplicate.')
                raise DuplicateTweet
            else:
                self.logger.error('Error code {} not recognized'.format(code_error))
            raise TweetNotSent

    def delete_last_tweets(self, count=1):
        self.logger.info("Deleting last {} tweets".format(count))
        r = self.api.request('statuses/user_timeline', {'count': count})
        if r.status_code == 200:
            for item in r:
                tweet_id = item['id']
                r2 = self.api.request('statuses/destroy/:%d' % tweet_id)
                if r2.status_code != 200:
                    self.logger.error("Posting tweet failed with code {}".format(r.status_code))
                    self.logger.error("Response content {}".format(r.response.content))
                    raise TwitterError
        else:
            self.logger.error("Response content {}".format(r.response.content))
            raise TwitterError
        return True

    def send_dm(self, username, message):
        user_id = self.get_user_id(username)
        event = {
            "event": {
                "type": "message_create",
                "message_create": {
                    "target": {"recipient_id": user_id},
                    "message_data": {"text": message}
                }}}
        r = self.api.request('direct_messages/events/new', json.dumps(event))
        if r.status_code != 200:
            self.logger.error("Direct Message failed {}".format(r.status_code))
            self.logger.error("Response content {}".format(r.response.content))
            raise TwitterError

    def get_user_id(self, username):
        r = self.api.request('users/lookup', {'screen_name': username.strip('@')})
        if r.status_code == 200:
            return r.json()[0]['id']
        self.logger.error("Getting User id failed with code {}".format(r.status_code))
        self.logger.error("Response content {}".format(r.response.content))
        return None


class LawsuitsTwitter(Twitter):
    def __init__(self, config_json_file):
        Twitter.__init__(self, config_json_file)
        self.templates = {"new_drug_single_hit": {
                                                "main": "{} case found! New #lawsuit by {}.",
                                                "additional": " Follow {} to learn more!"},
                          "new_drug_multiple_hits": {
                                                "main": "{} case found! New #lawsuit on {} pages!",
                                                "additional": " {} is one of them, follow {} to learn more!"},
                          "old_drug_new_source": {
                                                "main": "Another law firm, {}, started a case against {}, totaling to {} lawsuits.",
                                                "additional": " Follow {} to learn more!"},
                          "old_drug_new_sources": {
                                                "main": "New law firms started case against {}, totaling to {} lawsuits.",
                                                "additional": " {} is one of them, follow {} to learn more!"}
                          }

    def get_new_drug_single_hit_tweet(self, lawsuit_name, hit_details):
        source = hit_details['new_sources'][0]
        tweet = self.templates["new_drug_single_hit"]["main"].format(lawsuit_name, source.display_name)
        additional = self.templates["new_drug_single_hit"]["additional"].format(source.url)
        if (len(tweet) + self.url_length + len(additional)) < 280:
            return tweet + additional
        return tweet

    def get_new_drug_multiple_hits_tweet(self, lawsuit_name, hit_details):
        tweet = self.templates["new_drug_multiple_hits"]["main"].format(lawsuit_name, len(hit_details['new_sources']))
        random_src = self.scramble_list(hit_details['new_sources'])[0]
        additional = self.templates["new_drug_multiple_hits"]["additional"].format(random_src.display_name, random_src.url)

        return tweet + additional

    def get_old_drug_new_source_tweet(self, lawsuit_name, hit_details):
        source = hit_details['new_sources'][0]
        tweet = self.templates["old_drug_new_source"]["main"].format(source.display_name,
                                                             lawsuit_name,
                                                             len(hit_details['new_sources']) + len(hit_details['old_sources']))
        additional = self.templates["old_drug_new_source"]["additional"].format(source.url)
        return tweet + additional

    def get_old_drug_new_sources_tweet(self, lawsuit_name, hit_details):
        tweet = self.templates["old_drug_new_sources"]["main"].format(lawsuit_name,
                                                                      len(hit_details['new_sources']) + len(hit_details['old_sources']))
        random_src = self.scramble_list(hit_details['new_sources'])[0]
        additional = self.templates["old_drug_new_sources"]["additional"].format(random_src.display_name,
                                                                                   random_src.url)
        return tweet + additional

    def prepare_tweets(self, new_hits):
        tweets = []
        for lawsuit_name, hit_details in new_hits.items():
            if hit_details['first_hit'] is True and len(hit_details['new_sources']) == 1:
                tweet = self.get_new_drug_single_hit_tweet(lawsuit_name, hit_details)

            elif hit_details['first_hit'] is True and len(hit_details['new_sources']) != 1:
                tweet = self.get_new_drug_multiple_hits_tweet(lawsuit_name, hit_details)

            elif hit_details['first_hit'] is False and len(hit_details['new_sources']) == 1:
                tweet = self.get_old_drug_new_source_tweet(lawsuit_name, hit_details)

            elif hit_details['first_hit'] is False and len(hit_details['new_sources']) > 1:
                tweet = self.get_old_drug_new_sources_tweet(lawsuit_name, hit_details)

            elif hit_details['first_hit'] is False and len(hit_details['new_sources']) == 0:
                continue
            else:
                print(hit_details)
                raise NotImplementedError
            tweets.append(tweet)
        return tweets

    @staticmethod
    def scramble_list(list_orig):
        tmp = list_orig[:]
        random.shuffle(tmp)
        return tmp

    def admin_fix_me_dm(self, reason=None):
        message = "I'm broken, fix me. "
        if reason:
            message += reason
        self.send_dm(self.admin_profile, message)

if __name__ == '__main__':
    pass
