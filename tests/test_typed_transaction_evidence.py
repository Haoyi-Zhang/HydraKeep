import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_typed_transactions import typed_json_equal, validate


class TypedTransactionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in
                    (ROOT / 'results' / 'typed-transactions' / 'runs.jsonl').read_text().splitlines()
                    if line.strip()]

    def test_complete_factorial_evidence(self):
        self.assertEqual(len(self.rows), 128)
        self.assertEqual(len(validate(self.rows)), 64)

    def test_smoke_profile_keeps_strict_row_validation(self):
        rows = copy.deepcopy([row for row in self.rows
             if row['pattern'] in ('typed-snapshot', 'checkbox-coercion', 'scoped-submit', 'replacement')
             and row['gap'] == 'pre' and row['dispatch_order'] == ['t2', 't1'] and row['rep'] == 0])
        self.assertEqual(len(rows), 8)
        self.assertEqual(len(validate(rows, profile='smoke')), 8)
        with self.assertRaises(ValueError):
            validate(rows)
        with self.assertRaises(ValueError):
            validate(rows[:-1], profile='smoke')
        rows[0]['server_records'][0]['body'] = '{}'
        with self.assertRaises(ValueError):
            validate(rows, profile='smoke')

    def test_missing_and_duplicate_cells(self):
        with self.assertRaises(ValueError):
            validate(self.rows[:-1])
        with self.assertRaises(ValueError):
            validate(self.rows + [self.rows[0]])

    def test_receiver_body_tamper(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['server_records'][0]['body'] = '{}'
        with self.assertRaises(ValueError):
            validate(rows)

    def test_dispatch_tamper(self):
        rows = copy.deepcopy(self.rows)
        dispatch = next(event for event in rows[0]['trace'] if event['type'] == 'dispatch')
        dispatch['body'] = '{}'
        with self.assertRaises(ValueError):
            validate(rows)

    def test_receipt_type_tamper(self):
        rows = copy.deepcopy(self.rows)
        receipt = next(event for event in rows[0]['trace'] if event['type'] == 'receipt')
        receipt['payload']['agree'] = 1
        with self.assertRaises(ValueError):
            validate(rows)

    def test_untrusted_edit_rejected(self):
        rows = copy.deepcopy(self.rows)
        edit = next(event for event in rows[0]['trace'] if event['type'] == 'edit')
        edit['trusted'] = False
        with self.assertRaises(ValueError):
            validate(rows)

    def test_wrong_case_metadata_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['pattern'] = 'different-workflow'
        with self.assertRaises(ValueError):
            validate(rows)

    def test_hidden_browser_error_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['page_errors'] = ['synthetic error']
        with self.assertRaises(ValueError):
            validate(rows)

    def test_type_sensitive_json(self):
        self.assertFalse(typed_json_equal({'x': True}, {'x': 1}))
        self.assertFalse(typed_json_equal({'x': 1}, {'x': 1.0}))
        self.assertTrue(typed_json_equal({'x': [False], 'y': None},
                                         {'y': None, 'x': [False]}))


if __name__ == '__main__':
    unittest.main()
