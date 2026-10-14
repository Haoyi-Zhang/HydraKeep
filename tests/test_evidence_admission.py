"""Benign in-memory protocol regressions, not vulnerability execution."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from evidence_admission import admit_browser_trace, admit_edits, admit_transactions

CONTRACT = dict(fields={'a': {}}, consumers={
    'save': dict(fields=['a'], release_display=[], channel='application')})


def trace(value='toy'):
    field = dict(id='a', node=1, value=value, disabled=False, readOnly=False)
    def event(kind, **data):
        return dict(type=kind, fields=[dict(field)], **data)
    return [event('edit-start', field='a', node=1, requested=value, action=1),
            event('native-input', field='a', node=1, eventValue=value,
                  sequence=1, trusted=True, action=1),
            event('edit', field='a', requested=value, trusted=True, action=1, nativeSequence=1),
            event('consume', transaction='t1', consumer='save'),
            event('dispatch', transaction='t1', consumer='save', body='{"a":"toy"}'),
            event('ack', transaction='t1', consumer='save'),
            event('receipt', transaction='t1', consumer='save', channel='application', payload={'a':value})]


class EvidenceAdmissionTests(unittest.TestCase):
    def test_complete_chain(self):
        self.assertEqual(admit_browser_trace(trace(), CONTRACT), 1)

    def test_missing_native_event(self):
        rows = trace(); del rows[1]
        with self.assertRaisesRegex(ValueError, 'native value'):
            admit_browser_trace(rows, CONTRACT)

    def test_legacy_self_attested_edit_is_not_admitted(self):
        with self.assertRaisesRegex(ValueError, 'fresh matching action'):
            admit_browser_trace(trace()[2:], CONTRACT)

    def test_native_trust_and_value_bindings(self):
        for key, value in [('trusted', False), ('eventValue', 'other'),
                           ('node', 2), ('action', 2), ('sequence', None), ('field', 'other')]:
            with self.subTest(key=key):
                rows = trace(); rows[1][key] = value
                with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_bool_is_not_numeric_native_value(self):
        rows = trace(True); rows[1]['eventValue'] = 1
        with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_action_and_sequence_identifiers_do_not_coerce_boolean_or_float(self):
        for index, key, value in [(1,'action',True),(2,'action',1.0),
                                  (2,'nativeSequence',True),(1,'node',True)]:
            rows=trace(); rows[index][key]=value
            with self.assertRaises(ValueError):admit_browser_trace(rows,CONTRACT)

    def test_consistently_malformed_node_identity_is_not_action_evidence(self):
        for node in (True, False, 1.0, '1', 0, -1, None, [], {}):
            with self.subTest(node=node):
                rows=trace()
                for event in rows:
                    for item in event['fields']:
                        item['node']=copy.deepcopy(node)
                    if 'node' in event:
                        event['node']=copy.deepcopy(node)
                with self.assertRaisesRegex(ValueError, 'positive integer'):
                    admit_browser_trace(rows,CONTRACT)

    def test_completion_sequence_cannot_name_a_different_event(self):
        rows = trace(); rows[2]['nativeSequence'] = 7
        with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_request_and_start_cannot_diverge(self):
        rows = trace(); rows[0]['requested'] = 'other'
        with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_reused_completion(self):
        rows = trace(); rows.insert(3, copy.deepcopy(rows[2]))
        with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_reused_sequence(self):
        rows = trace(); rows.insert(2, copy.deepcopy(rows[1]))
        with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_partial_native_values_can_precede_completed_value(self):
        rows = trace(); partial = copy.deepcopy(rows[1]); partial['eventValue'] = 't'
        partial['fields'][0]['value'] = 't'; rows[1]['sequence'] = 2; rows[2]['nativeSequence'] = 2
        rows.insert(1, partial)
        self.assertEqual(admit_browser_trace(rows, CONTRACT), 1)

    def test_noop_does_not_manufacture_edit(self):
        rows = trace(); del rows[1]; rows[1].update(type='edit-noop', trusted=False, nativeSequence=None)
        self.assertEqual(admit_browser_trace(rows, CONTRACT), 0)

    def test_receipt_before_consumption(self):
        rows = trace(); rows[3], rows[6] = rows[6], rows[3]
        with self.assertRaisesRegex(ValueError, 'inverted'):
            admit_browser_trace(rows, CONTRACT)

    def test_dispatch_before_consumption(self):
        rows = trace(); rows[3], rows[4] = rows[4], rows[3]
        with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_receipt_before_dispatch_or_ack(self):
        for index in (4, 5):
            rows = trace(); rows[index], rows[6] = rows[6], rows[index]
            with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_other_transaction_receipt_order_is_valid(self):
        rows = trace(); second = copy.deepcopy(rows[3:]);
        for event in second: event['transaction'] = 't2'
        rows = rows[:4] + second[:1] + second[1:] + rows[4:]
        self.assertEqual(admit_browser_trace(rows, CONTRACT), 1)

    def test_missing_duplicate_or_wrong_consumer_event(self):
        for mutation in ('missing', 'duplicate', 'consumer'):
            rows = trace()
            if mutation == 'missing': del rows[5]
            elif mutation == 'duplicate': rows.insert(5, copy.deepcopy(rows[4]))
            else: rows[4]['consumer'] = 'other'
            with self.assertRaises(ValueError): admit_browser_trace(rows, CONTRACT)

    def test_all_512_typed_completions_bind_native_values_and_trust(self):
        rows = [json.loads(line) for line in
                (ROOT / 'results/typed-transactions/runs.jsonl').read_text().splitlines()]
        contracts = json.loads((ROOT / 'fixtures/typed-transactions/contracts.json').read_text())
        count = 0
        for row in rows:
            for completion in row['trace']:
                if completion['type'] != 'edit': continue
                count += 1
                for change in ('value', 'trust'):
                    observed = copy.deepcopy(row['trace'])
                    native = next(e for e in observed if e['type'] in ('native-input', 'native-change')
                                  and e['sequence'] == completion['nativeSequence'])
                    if change == 'value': native['eventValue'] = 'mismatching-native-value'
                    else: native['trusted'] = False
                    with self.assertRaises(ValueError):
                        admit_browser_trace(observed, contracts[row['case']])
        self.assertEqual(count, 512)

    def test_all_256_runs_reject_inverted_consumption_receipt_pairs(self):
        count = 0
        for family, filename in [('transactions', 'transactions.jsonl'),
                                 ('typed-transactions', 'runs.jsonl')]:
            contracts = json.loads((ROOT / 'fixtures' / family / 'contracts.json').read_text())
            for line in (ROOT / 'results' / family / filename).read_text().splitlines():
                row = json.loads(line); observed = copy.deepcopy(row['trace'])
                first = next(i for i, e in enumerate(observed) if e['type'] == 'consume')
                last = next(i for i, e in enumerate(observed) if e['type'] == 'receipt'
                            and e['transaction'] == observed[first]['transaction'])
                observed[first], observed[last] = observed[last], observed[first]
                with self.assertRaises(ValueError):
                    admit_browser_trace(observed, contracts[row['case']])
                count += 1
        self.assertEqual(count, 256)

    def test_native_post_rows_have_action_bindings_and_real_receivers(self):
        contracts=json.loads((ROOT/'fixtures/native/native-submit-contracts.json').read_text())
        count=0
        for line in (ROOT/'results/native-integration/native-submit-chromium.jsonl').read_text().splitlines():
            row=json.loads(line);admit_edits(row['trace'],contracts[row['case']])
            self.assertEqual(row['server_records'][0]['run'],row['run'])
            self.assertTrue(row['server_records'][0]['contentType'].startswith('application/x-www-form-urlencoded'))
            consume=next(i for i,e in enumerate(row['trace']) if e['type']=='consume')
            receipt=next(i for i,e in enumerate(row['trace']) if e['type']=='receipt')
            self.assertLess(consume,receipt);count+=1
        self.assertEqual(count,56)


if __name__ == '__main__': unittest.main()
