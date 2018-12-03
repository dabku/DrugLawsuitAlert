import unittest
from database.lawsuit_database import DrugsDb, DbHit, DbDrug, DbSource, NoResultFound


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'unittests')

        try:
            os.mkdir(db_path)
        except FileExistsError:
            pass
        cls.test_run_db = os.path.join(db_path, 'unittest.db')
        try:
            os.remove(cls.test_run_db)
        except FileNotFoundError:
            pass

        cls.db = DrugsDb(db_name='unittest.db', db_path=db_path)
        cls.db.create_database()
        cls.session = cls.db.create_session()
        test_objects = [DbDrug('First Drug'),
                        DbDrug('Second Drug'),
                        DbDrug('Third Drug'),
                        DbDrug('Orphan Drug'),
                        DbSource('First Source', 'http://FirstSource.com', 'First Attorneys', '@FirstSource', 1, 2),
                        DbSource('Second Source', 'http://SecondSource.com', 'Second Attorneys', '@SecondSource', 3, 4),
                        DbSource('Third Source', 'http://ThirdSource.com', 'Third Attorneys', '@ThirdSource', 5, 6),
                        DbHit(1, 1, 1),
                        DbHit(1, 1, 2),
                        DbHit(1, 1, 3),
                        DbHit(1, 2, 3),
                        DbHit(1, 2, 4),
                        DbHit(1, 3, 4),
                        DbHit(2, 1, 4),
                        DbHit(3, 3, 4)]

        for obj in test_objects:
            cls.db.add_item(obj, cls.session)
            pass

    @classmethod
    def tearDownClass(cls):
        import os
        cls.session.close()
        cls.db.close_db()
        os.remove(cls.test_run_db)


class TestDatabaseReadOperations(TestDatabase):

    def test_get_drug_id(self):
        self.assertEqual(self.db.get_drug(self.session, db_id=1).name, 'First Drug')
        self.assertRaises(NoResultFound, self.db.get_drug, self.session, db_id=999)

    def test_get_drug_name(self):
        self.assertEqual(self.db.get_drug(self.session, name='First Drug').name, 'First Drug')
        self.assertRaises(NoResultFound, self.db.get_drug, self.session, name='NO drug')

    def test_get_source_id(self):
        self.assertEqual(self.db.get_source(self.session, db_id=1).name, 'First Source')
        self.assertRaises(NoResultFound, self.db.get_source, self.session, db_id=999)

    def test_get_source_name(self):
        self.assertEqual(self.db.get_source(self.session, name='First Source').name, 'First Source')
        self.assertRaises(NoResultFound, self.db.get_source, self.session, name='NO source')

    def test_get_distinct_drug_hits(self):
        self.assertEqual(self.db.get_distinct_drug_hits(self.session), [1, 2, 3])

    def test_get_sources_ids_for_drug(self):
        self.assertEqual(self.db.get_sources_ids_for_drug(self.session, 1), [1, 2, 3])
        self.assertEqual(self.db.get_sources_ids_for_drug(self.session, 2), [1])
        self.assertEqual(self.db.get_sources_ids_for_drug(self.session, 3), [3])
        self.assertEqual(self.db.get_sources_ids_for_drug(self.session, 4), [])

    def test_get_sources_names_for_drug(self):
        self.assertEqual(self.db.get_sources_names_for_drug(self.session, 1),
                         ['First Source', 'Second Source', 'Third Source'])
        self.assertEqual(self.db.get_sources_names_for_drug(self.session, 2), ['First Source'])
        self.assertEqual(self.db.get_sources_names_for_drug(self.session, 3), ['Third Source'])
        self.assertEqual(self.db.get_sources_names_for_drug(self.session, 4), [])

    def test_get_hits_for_drug_and_source(self):
        self.assertRaises(NoResultFound, self.db.get_hits_for_drug_and_source, self.session, None, None)
        r = self.db.get_hits_for_drug_and_source(self.session, 1, None)
        self.assertEqual(sorted([item.id for item in r]), [1, 2, 3, 4, 5, 6])
        r = self.db.get_hits_for_drug_and_source(self.session, None, 1)
        self.assertEqual(sorted([item.id for item in r]), [1, 2, 3, 7])
        r = self.db.get_hits_for_drug_and_source(self.session, 1, 1)
        self.assertEqual(sorted([item.id for item in r]), [1, 2, 3])
        self.assertRaises(NoResultFound, self.db.get_hits_for_drug_and_source, self.session, 4, None)
        self.assertRaises(NoResultFound, self.db.get_hits_for_drug_and_source, self.session, 999, None)

    def test_get_hit_stats_for_drug_and_source(self):
        self.assertEqual(self.db.get_hit_stats_for_drug_and_source(self.session, 1, 1), (3, 6))
        self.assertEqual(self.db.get_hit_stats_for_drug_and_source(self.session, 1, 2), (2, 6))
        self.assertEqual(self.db.get_hit_stats_for_drug_and_source(self.session, 1, 3), (1, 6))
        self.assertEqual(self.db.get_hit_stats_for_drug_and_source(self.session, 1, 4), (0, 6))
        self.assertEqual(self.db.get_hit_stats_for_drug_and_source(self.session, 999, 999), (0, 0))


class TestDatabaseWriteOperations(TestDatabase):
    def test_optimize_hits_table(self):
        self.db.optimize_hits_table(self.session)
        self.assertEqual(self.db.optimize_hits_table(self.session), None)
        r = self.db.get_hits_for_drug_and_source(self.session, 1, 1)
        self.assertEqual(sorted([item.id for item in r]), [1, 3])
        r = self.db.get_hits_for_drug_and_source(self.session, 1, 2)
        self.assertEqual(sorted([item.id for item in r]), [4, 5])
        r = self.db.get_hits_for_drug_and_source(self.session, 3, 3)
        self.assertEqual(sorted([item.id for item in r]), [8])

        self.assertRaises(NoResultFound, self.db.get_hits_for_drug_and_source, self.session, 3, 1)
        self.assertRaises(NoResultFound, self.db.get_hits_for_drug_and_source, self.session, 999, 1)

    def test_add_sources_if_not_in_db(self):
        sources = []

        class MockClass:
            def __init__(self, text):
                self.name = self.url = self.display_name = self.twitter_name = text
                self.scan_ts = 0
        sources.append((MockClass('AAAA'), 0))
        sources.append((MockClass('BBBB'), 0))

        self.assertEqual(self.db.add_sources_if_not_in_db(sources, self.session), {'AAAA': 4, 'BBBB': 5})
        self.assertEqual(self.db.get_source(self.session, name='AAAA').updated_ts, 0)
        # test updating timestamp
        source = [(MockClass('AAAA'), 123456789)]
        self.assertEqual(self.db.add_sources_if_not_in_db(source, self.session), {'AAAA': 4})
        self.assertEqual(self.db.get_source(self.session, name='AAAA').updated_ts, 123456789)

    def test_add_drugs_if_not_in_db(self):
        drugs = ['AAAA', 'BBBB']
        self.assertEqual(self.db.add_drugs_if_not_in_db(drugs, self.session), {'AAAA': 5, 'BBBB': 6})


if __name__ == "__main__":

    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestDatabaseReadOperations))
    test_suite.addTest(unittest.makeSuite(TestDatabaseWriteOperations))
    unittest.TextTestRunner(verbosity=2).run(test_suite)
