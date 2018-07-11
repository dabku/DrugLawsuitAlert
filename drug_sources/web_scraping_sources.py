import requests
import time
import urllib
import sys
import os
import inspect
from bs4 import BeautifulSoup
import logging


class HTML_RetrievalFail(Exception):
    pass


class NoDrugsFound(Exception):
    pass


class Source:
    _url = "None"
    _test_file = "None"
    _display_name = "None"
    _twitter_name = "None"

    def __init__(self):
        self.logger = logging.getLogger('__main__')
        pass

    def update_test_file(self):
        self.logger.info("Updating test file for source {}".format(self.display_name))
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'}
        self.logger.debug("Downloading HTML file")
        r = requests.get(self.url, headers=headers).content
        directory = os.path.split(self.test_file)[0]
        try:
            os.makedirs(directory)
        except FileExistsError:
            pass
        with open(self.test_file, 'bw') as html_file:
            self.logger.debug("Saving HTML file: {}".format(self.test_file))
            html_file.write(r)

    def get_data(self, url, from_file=False):
        if not from_file:
            self.logger.debug('Getting data from url: {}'.format(url))
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'}
                r = requests.get(url, headers=headers).content
            except requests.exceptions.ConnectionError:
                raise HTML_RetrievalFail("Failed to get HTML from the web: {}".format(url))
        else:
            self.logger.debug('Getting data from file: {}'.format(url))
            try:
                with open(url, 'r', encoding='utf8') as in_file:
                    r = in_file.read()
            except FileNotFoundError:
                raise HTML_RetrievalFail("Failed to get HTML from the file: {}".format(url))
        return r

    def fetch_drugs_from_source(self, from_file=False):
        raise NotImplementedError

    def get_drugs(self, from_file=False):
        self.logger.info("Reading drugs from {}".format(self.display_name))
        response = dict()
        try:
            response["drugs"] = self.fetch_drugs_from_source(from_file)
        except AttributeError:
            raise NoDrugsFound('Failed getting drugs for {}'.format(self.url))
        self.logger.info("Got {} entries".format(len(response["drugs"])))
        response["source"] = self
        response["ts"] = int(time.time())
        if len(response["drugs"]) == 0:
            raise NoDrugsFound
        return response

    @property
    def url(self):
        return self._url

    @property
    def test_file(self):
        path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(path, self._test_file)

    @property
    def display_name(self):
        return self._display_name

    @property
    def twitter_name(self):
        return self._twitter_name

    @property
    def name(self):
        return self.__class__.__name__


class TorHoermanLawSource(Source):
    _url = "https://www.torhoermanlaw.com/lawsuits/"
    _test_file = "test_sites/torhoermanlaw/torhoermanlaw.html"
    _display_name = "Tor Hoerman Law LLC"

    def __init__(self):
        Source.__init__(self)
        pass

    def fetch_drugs_from_source(self, from_file=False):
        drugs_dict = {}
        if from_file:
            url = self.test_file
        else:
            url = self.url
        r = self.get_data(url, from_file=from_file)
        soup = BeautifulSoup(r, 'html.parser')
        drugs = soup.find('div', class_="mainContent")
        drugs = drugs.find_all('a')
        for item in drugs:
            drug_name = item.text.strip()
            try:
                drug_link = item.get("href")
                drug_link = urllib.parse.urljoin(self.url, drug_link)
            except AttributeError:
                continue
            drugs_dict[drug_name] = drug_link
        return drugs_dict


class TheJusticeSource(Source):
    _url = "https://www.thejusticelawyer.com/practice-areas/detail/dangerous-drugs-medical-devices-list"
    _test_file = "test_sites/thejustice/thejustice.html"
    _display_name = "The Eichholz Law Firm, P.C."

    def __init__(self):
        Source.__init__(self)
        pass

    def fetch_drugs_from_source(self, from_file=False):
        drugs_dict = {}
        if from_file:
            url = self.test_file
        else:
            url = self.url
        r = self.get_data(url, from_file=from_file)
        soup = BeautifulSoup(r, 'html.parser')
        drugs = soup.find_all('h3')

        for item in drugs:
            drug_name = item.text
            try:
                drug_link = item.find('a').get("href")
            except AttributeError:
                continue
            drugs_dict[drug_name] = drug_link
        return drugs_dict


class DrugLawsuitSource(Source):
    _url = "https://www.druglawsuitsource.com/drugs/"
    _test_file = "test_sites/druglawsuitsource/druglawsuitsource.html"
    _display_name = "Buckfire & Buckfire, P.C"

    def __init__(self):
        Source.__init__(self)
        pass

    def fetch_drugs_from_source(self, from_file=False):
        drugs_dict = {}
        if from_file:
            url = self.test_file
        else:
            url = self.url
        r = self.get_data(url, from_file=from_file)
        soup = BeautifulSoup(r, 'html.parser')
        drugs = soup.find_all('td', class_="column-1")

        for item in drugs:
            drug_name = item.text
            try:
                drug_link = item.find('a').get("href")
            except AttributeError:
                continue
            drugs_dict[drug_name] = drug_link
        return drugs_dict


class LevinLawSource(Source):
    _url = "https://www.levinlaw.com/drug-injuries"
    _test_file = "test_sites/levinlaw/levinlaw.html"
    _display_name = "Levin Papantonio"
    discarded = ['MAIN OFFICE', 'Click to Chat', 'Click for Free Evaluation']
    def __init__(self):
        Source.__init__(self)
        pass

    def fetch_drugs_from_source(self, from_file=False):
        drugs_dict = {}
        if from_file:
            url = self.test_file
        else:
            url = self.url
        r = self.get_data(url, from_file=from_file)
        soup = BeautifulSoup(r, 'html.parser')
        drugs = soup.find_all('div', class_="one-third-column")
        drugs = [item.find('span') for item in drugs]
        drugs = [item.get_text().strip() for item in drugs]

        for item in drugs:
            if item not in self.discarded:
                drugs_dict[item]=self.url
            pass
        return drugs_dict


class ClassActionSource(Source):
    _url = "https://www.classaction.com/lawsuits/drugs/"
    _test_file = "test_sites/classaction/classaction.html"
    _display_name = "Morgan & Morgan, PA"

    def __init__(self):
        Source.__init__(self)
        pass

    def fetch_drugs_from_source(self, from_file=False):
        drugs_dict = {}
        if from_file:
            url = self.test_file
        else:
            url = self.url
        r = self.get_data(url, from_file=from_file)

        soup = BeautifulSoup(r, 'html.parser')
        drug_entries = soup.find_all('div', class_="blurb-wrapper")

        for item in drug_entries:
            dr = item.find('h4').text.replace(' Lawsuit', '')
            drugs_dict[dr] = item['data-url']
        return drugs_dict


class YouHaveALawyer(Source):
    _url = "https://www.youhavealawyer.com/side-effects/"
    _test_file = "test_sites/youhavealawyer/youhavealawyer.html"
    _display_name = "Saiontz & Kirk, P.A."

    def __init__(self):
        Source.__init__(self)
        pass

    def fetch_drugs_from_source(self, from_file=False):
        drugs_dict = {}
        if from_file:
            url = self.test_file
        else:
            url = self.url
        r = self.get_data(url, from_file=from_file)
        soup = BeautifulSoup(r, 'html.parser')
        items = soup.find_all('div', class_="fusion-toggle-heading")
        drugs = [drug.text for drug in items]
        for drug in drugs:
            drugs_dict[drug] = self.url
        return drugs_dict


class ForTheInjured(Source):
    _url = "https://www.fortheinjured.com/class-action-lawyers/defective-drugs/"
    _test_file = "test_sites/fortheinjured/fortheinjured.html"
    _display_name = "Gordon & Doner, P.A."

    def __init__(self):
        Source.__init__(self)
        pass

    def fetch_drugs_from_source(self, from_file=False):
        drugs_dict = {}
        if from_file:
            url = self.test_file
        else:
            url = self.url
        r = self.get_data(url, from_file=from_file)
        soup = BeautifulSoup(r, 'html.parser')
        hits = soup.find_all('div', class_="class-thumb")
        for hit in hits:
            drug_name = hit.find('a')['title']
            drug_link =  urllib.parse.urljoin("{0.scheme}://{0.netloc}/".format(urllib.parse.urlsplit(self.url)),
                                              hit.find('a')['href'])
            drugs_dict[drug_name] = drug_link
        return drugs_dict


def get_all_scraping_sources():
    srcs = dict()
    class_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
    for name, scraping_class in class_members:
        if issubclass(scraping_class, Source) and name != 'Source':
            srcs[name] = scraping_class
    return srcs


def update_test_sources():
    srcs = get_all_scraping_sources()
    for src_class in srcs.values():
        src_class().update_test_file()


if __name__ == '__main__':
    pass
