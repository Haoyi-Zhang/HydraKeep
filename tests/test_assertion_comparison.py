import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from compare_playwright_assertions import validate


class AssertionComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in
                    (ROOT/'results/assertion-comparison/runs.jsonl').read_text().splitlines()]

    def test_same_execution_coverage_and_agreement(self):
        self.assertEqual(validate(self.rows),48)
        self.assertEqual(sum(r['oracle']['status']=='clean' for r in self.rows),16)
        self.assertEqual(sum(r['oracle']['status']=='violation' for r in self.rows),32)
        self.assertTrue(all(r['oracle']['status']==r['assertions']['status'] for r in self.rows))

    def test_missing_duplicate_or_changed_receiver_rejected(self):
        for rows in (self.rows[:-1], self.rows+[self.rows[0]]):
            with self.assertRaises(ValueError):validate(rows)
        rows = copy.deepcopy(self.rows); rows[0]['server_records'][0]['body']='{}'
        with self.assertRaises(ValueError):validate(rows)


if __name__=='__main__': unittest.main()
