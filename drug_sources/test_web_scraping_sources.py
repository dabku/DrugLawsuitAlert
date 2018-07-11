import unittest
from .web_scraping_sources import get_all_scraping_sources


class TestScrapingSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = []
        srcs = get_all_scraping_sources()
        for src_class in srcs.values():
            cls.sources.append(src_class())


class TestOffline(TestScrapingSources):

    def test_fetch_data_file(self):
        for src in self.sources:
            with self.subTest(name=type(src)):
                src.get_data(url=src.test_file, from_file=True)

    def test_get_drugs_file(self):
        for src in self.sources:
            with self.subTest(name=type(src)):
                drugs = src.get_drugs(from_file=True)
                self.assertIsNotNone(drugs)


class TestOnline(TestScrapingSources):
    # @unittest.skip("online tests disabled")
    def test_fetchdata_url(self):
        for src in self.sources:
            with self.subTest(name=type(src)):
                src.get_data(url=src.url, from_file=False)

    # @unittest.skip("online tests disabled")
    def test_get_drugs_url(self):
        for src in self.sources:
            with self.subTest(name=type(src)):
                drugs = src.get_drugs(from_file=False)
                self.assertIsNotNone(drugs)

if __name__ == '__main__':

    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestOnline))
    test_suite.addTest(unittest.makeSuite(TestOffline))
    unittest.TextTestRunner(verbosity=2).run(test_suite)
