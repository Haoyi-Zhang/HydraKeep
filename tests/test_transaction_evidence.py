import copy
import importlib.util
import json
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_transactions import validate, typed_json_equal


class TransactionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[json.loads(l) for l in (ROOT/'results/transactions/transactions.jsonl').read_text().splitlines()]

    def test_complete_evidence(self):
        self.assertEqual(len(validate(self.rows)),64)

    def test_missing_cell(self):
        with self.assertRaises(ValueError):validate(self.rows[:-1])

    def test_duplicate_cell(self):
        with self.assertRaises(ValueError):validate(self.rows+[self.rows[0]])

    def test_tampered_receiver_body(self):
        rows=copy.deepcopy(self.rows);rows[0]['server_records'][0]['body']='{}'
        with self.assertRaises(ValueError):validate(rows)

    def test_tampered_consumer_identity(self):
        rows=copy.deepcopy(self.rows);rows[0]['server_records'][0]['consumer']='wrong'
        with self.assertRaises(ValueError):validate(rows)

    def test_missing_receiver(self):
        rows=copy.deepcopy(self.rows);rows[0]['server_records'].pop()
        with self.assertRaises(ValueError):validate(rows)

    def test_tampered_stored_verdict(self):
        rows=copy.deepcopy(self.rows);rows[0]['oracle']['status']='violation'
        with self.assertRaises(ValueError):validate(rows)

    def test_tampered_reference(self):
        rows=copy.deepcopy(self.rows);rows[0]['reference']['receipts']=1
        with self.assertRaises(ValueError):validate(rows)

    def test_hidden_browser_error(self):
        rows=copy.deepcopy(self.rows);rows[0]['page_errors']=['test error']
        with self.assertRaises(ValueError):validate(rows)

    def test_duplicate_run_identity(self):
        rows=copy.deepcopy(self.rows);rows[1]['run']=rows[0]['run']
        with self.assertRaises(ValueError):validate(rows)

    def test_type_sensitive_json(self):
        self.assertFalse(typed_json_equal({'x':[True]}, {'x':[1]}))
        self.assertFalse(typed_json_equal({'x':1}, {'x':1.0}))
        self.assertTrue(typed_json_equal({'x':[1], 'y':None}, {'y':None, 'x':[1]}))

    def test_coerced_receiver_value(self):
        rows=copy.deepcopy(self.rows)
        receipt=next(e for e in rows[0]['trace'] if e['type']=='receipt')
        dispatch=next(e for e in rows[0]['trace'] if e['type']=='dispatch')
        receipt['payload']['extra']=1
        body=json.loads(dispatch['body']);body['extra']=True
        dispatch['body']=json.dumps(body)
        rows[0]['server_records'][0]['body']=json.dumps(body)
        with self.assertRaises(ValueError):validate(rows)

    def test_wrong_framework_metadata(self):
        rows=copy.deepcopy(self.rows);rows[0]['framework']='vue'
        with self.assertRaises(ValueError):validate(rows)

    def test_wrong_workflow_metadata(self):
        rows=copy.deepcopy(self.rows);rows[0]['pattern']='stale-closure'
        with self.assertRaises(ValueError):validate(rows)

    def test_wrong_evidence_class(self):
        rows=copy.deepcopy(self.rows);rows[0]['evidence_class']='native-SSR'
        with self.assertRaises(ValueError):validate(rows)

    def test_nonfinite_duration(self):
        rows=copy.deepcopy(self.rows);rows[0]['duration_ms']=float('nan')
        with self.assertRaises(ValueError):validate(rows)

    def test_boolean_duration(self):
        rows=copy.deepcopy(self.rows);rows[0]['duration_ms']=True
        with self.assertRaises(ValueError):validate(rows)
