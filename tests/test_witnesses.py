import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from witness import ObligationWitness, failure_key


class WitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = [json.loads(line) for line in
                       (ROOT / 'results' / 'witnesses' / 'witnesses.jsonl').read_text().splitlines()
                       if line.strip()]
        cls.contracts = {
            'transactions': json.loads(
                (ROOT / 'fixtures' / 'transactions' / 'contracts.json').read_text()),
            'typed-transactions': json.loads(
                (ROOT / 'fixtures' / 'typed-transactions' / 'contracts.json').read_text()),
        }

    def key(self, target):
        return (target['field'], target['kind'], str(target['phase']),
                target['epoch'], target['revision'], str(target['transaction']))

    def test_all_browser_failures_have_one_minimal_witnesses(self):
        self.assertEqual(len(self.records), 144)
        for record in self.records:
            contract = self.contracts[record['family']][record['case']]
            reducer = ObligationWitness(contract, self.key(record['target']))
            events = record['events']
            self.assertTrue(reducer.preserves(events), record['run'])
            self.assertTrue(record['one_minimal'])
            self.assertLess(len(events), record['original_events'])
            for index in range(len(events)):
                self.assertFalse(reducer.preserves(events[:index] + events[index + 1:]),
                                 (record['run'], index))

    def test_wrong_failure_key_is_not_preserved(self):
        record = self.records[0]
        contract = self.contracts[record['family']][record['case']]
        target = list(self.key(record['target']))
        target[0] = 'not-a-field'
        self.assertFalse(ObligationWitness(contract, tuple(target)).preserves(record['events']))

    def test_cache_preserves_witness_and_is_reset_between_calls(self):
        for record in self.records[:2]:
            contract = self.contracts[record['family']][record['case']]
            target = self.key(record['target'])
            cached = ObligationWitness(contract, target)
            direct = ObligationWitness(contract, target, memoize=False)
            first = cached.minimize(record['events'])
            other = direct.minimize(record['events'])
            again = cached.minimize(record['events'])
            self.assertEqual(first.indices, other.indices)
            self.assertEqual(first.events, other.events)
            self.assertEqual(first, again)
            self.assertLess(first.predicate_evaluations, other.predicate_evaluations)
            self.assertGreater(first.predicate_cache_hits, 0)

    def test_failure_key_is_type_stable(self):
        item = {'field': 'a', 'kind': 'consumer-only-loss', 'phase': 'receipt-t1',
                'epoch': 0, 'revision': 1, 'transaction': 't1'}
        self.assertEqual(failure_key(item),
                         ('a', 'consumer-only-loss', 'receipt-t1', 0, 1, 't1'))


if __name__ == '__main__':
    unittest.main()
