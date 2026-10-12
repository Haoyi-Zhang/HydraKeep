"""Benign input-boundary regressions; no browsers, servers, or output writes."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from evidence_admission import admit_browser_trace, admit_edits
from form_oracle import interpret_form
from transaction_oracle import interpret_transactions
from transaction_spec import specify
if __package__:
    from .test_evidence_admission import CONTRACT, trace as fixture_trace
else:
    from test_evidence_admission import CONTRACT, trace as fixture_trace


def action_trace(value='toy'):
    rows = fixture_trace(value)
    rows[4]['body'] = json.dumps({'a': value})
    return rows


class NativeActionBoundaryTests(unittest.TestCase):
    def test_later_same_field_event_requires_binding(self):
        for kind in ('native-input', 'native-change'):
            for binding in ('missing', 'null'):
                for trusted in (False, True):
                    with self.subTest(kind=kind, binding=binding, trusted=trusted):
                        rows = action_trace()
                        later = copy.deepcopy(rows[1])
                        later.update(type=kind, sequence=2, trusted=trusted)
                        if binding == 'missing':
                            del later['action']
                        else:
                            later['action'] = None
                        rows.insert(2, later)
                        with self.assertRaises(ValueError):
                            admit_browser_trace(rows, CONTRACT)

    def test_older_completion_reference_cannot_skip_later_bound_event(self):
        rows = action_trace()
        later = copy.deepcopy(rows[1])
        later.update(type='native-change', sequence=2)
        rows.insert(2, later)
        with self.assertRaisesRegex(ValueError, 'matching trusted native value'):
            admit_browser_trace(rows, CONTRACT)

    def test_latest_bound_same_value_event_remains_valid(self):
        for value in ('toy', '', True, False):
            with self.subTest(value=value):
                rows = action_trace(value)
                later = copy.deepcopy(rows[1])
                later.update(type='native-change', sequence=2)
                rows[2]['nativeSequence'] = 2
                rows.insert(2, later)
                self.assertEqual(admit_browser_trace(rows, CONTRACT), 1)
                self.assertEqual(interpret_transactions(rows, CONTRACT)['status'], 'clean')

    def test_later_bound_wrong_value_cannot_complete(self):
        rows = action_trace()
        later = copy.deepcopy(rows[1])
        later.update(sequence=2, eventValue='partial')
        later['fields'][0]['value'] = 'partial'
        rows[2]['nativeSequence'] = 2
        rows.insert(2, later)
        with self.assertRaisesRegex(ValueError, 'matching trusted native value'):
            admit_browser_trace(rows, CONTRACT)

    def test_actionless_other_field_does_not_replace_active_evidence(self):
        contract = copy.deepcopy(CONTRACT)
        contract['fields']['b'] = {}
        for binding in ('missing', 'null'):
            with self.subTest(binding=binding):
                rows = action_trace()
                other = dict(id='b', node=2, value='other', disabled=False, readOnly=False)
                for event in rows:
                    event['fields'].append(dict(other))
                change = copy.deepcopy(rows[1])
                change.update(type='native-change', field='b', node=2,
                              eventValue='other', sequence=2, trusted=False, action=None)
                if binding == 'missing':
                    del change['action']
                rows.insert(2, change)
                self.assertEqual(admit_browser_trace(rows, contract), 1)
                change['action'] = 1
                with self.assertRaises(ValueError):
                    admit_browser_trace(rows, contract)

    def test_actionless_events_outside_action_remain_allowed(self):
        for binding in ('missing', 'null'):
            with self.subTest(binding=binding):
                rows = action_trace()
                before = copy.deepcopy(rows[1])
                before.update(action=None, trusted=False, eventValue='seed')
                before['fields'][0]['value'] = 'seed'
                after = copy.deepcopy(rows[1])
                after.update(type='native-change', action=None, trusted=False, sequence=3)
                if binding == 'missing':
                    del before['action']
                    del after['action']
                rows[1]['sequence'] = 2
                rows[2]['nativeSequence'] = 2
                rows.insert(3, after)  # after completion, before consumption
                rows.insert(0, before)
                self.assertEqual(admit_browser_trace(rows, CONTRACT), 1)

    def test_unbound_native_event_cannot_be_downgraded_to_noop(self):
        for binding in ('missing', 'null'):
            for trusted in (False, True):
                with self.subTest(binding=binding, trusted=trusted):
                    rows = action_trace()
                    rows[1].update(action=None, trusted=trusted)
                    if binding == 'missing':
                        del rows[1]['action']
                    rows[2].update(type='edit-noop', trusted=False, nativeSequence=None)
                    with self.assertRaises(ValueError):
                        admit_browser_trace(rows, CONTRACT)

    def test_confirmed_noop_needs_no_native_event(self):
        rows = action_trace()
        del rows[1]
        rows[1].update(type='edit-noop', trusted=False, nativeSequence=None)
        self.assertEqual(admit_browser_trace(rows, CONTRACT), 0)

    def test_current_typed_matrix_rejects_later_unbound_event(self):
        from analyze_typed_transactions import CONTRACTS, validate
        original = [json.loads(line) for line in
                    (ROOT / 'results/typed-transactions/runs.jsonl').read_text().splitlines()]
        for binding in ('missing', 'null'):
            for trusted in (False, True):
                with self.subTest(binding=binding, trusted=trusted):
                    rows = copy.deepcopy(original)
                    row = rows[0]
                    events = row['trace']
                    completion = max(i for i, event in enumerate(events) if event['type'] == 'edit')
                    seq = events[completion]['nativeSequence']
                    native = next(i for i, event in enumerate(events) if event.get('sequence') == seq)
                    later = copy.deepcopy(events[native])
                    later.update(sequence=seq + 1, action=None, trusted=trusted)
                    if binding == 'missing':
                        del later['action']
                    for event in events[native + 1:]:
                        if event.get('sequence', 0) > seq:
                            event['sequence'] += 1
                        reference = event.get('nativeSequence')
                        if reference is not None and reference > seq:
                            event['nativeSequence'] += 1
                    events.insert(native + 1, later)
                    with self.assertRaises(ValueError):
                        admit_browser_trace(events, CONTRACTS[row['case']])
                    with self.assertRaises(ValueError):
                        validate(rows)


class ReadOnlyReadinessTests(unittest.TestCase):
    def observations(self, *, disabled=False, read_only=False, phase='pre'):
        control = dict(id='a', node=1, value='seed', control='text',
                       disabled=disabled, readOnly=read_only)

        def event(kind, **data):
            return dict(type=kind, phase=phase, fields=[dict(control)], **data)

        policy = {'a': dict(channel='native', unavailable_until_hydration=True)}
        rows = [event('checkpoint')]
        if disabled or read_only:
            rows.append(event('edit-blocked', field='a'))
        rows.extend([event('consume'), event('receipt', channel='native', payload={'a': 'seed'})])
        contract = dict(fields=policy, consumers={
            'terminal': dict(fields=['a'], release_display=['a'], channel='native')})
        explicit = []
        for original in rows:
            current = copy.deepcopy(original)
            if current['type'] in ('consume', 'receipt'):
                current.update(transaction='t1', consumer='terminal')
            if current['type'] == 'receipt':
                explicit.append(event('dispatch', transaction='t1', consumer='terminal',
                                      body=json.dumps({'a': 'seed'})))
                explicit.append(event('ack', transaction='t1', consumer='terminal'))
            explicit.append(current)
        return rows, policy, explicit, contract

    def compare_models(self, rows, policy, explicit, contract, expected):
        self.assertEqual(admit_edits(rows, policy), 0)
        self.assertEqual(admit_browser_trace(explicit, contract), 0)
        outputs = [interpret_form(rows, policy), interpret_transactions(explicit, contract),
                   specify(explicit, contract)]
        for result in outputs:
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['accepted_edits'], 0)
            self.assertFalse(result['unknown'])
        self.assertEqual([r['blocked_edits'] for r in outputs], [outputs[0]['blocked_edits']] * 3)
        self.assertEqual([{(f['field'], f['kind'], f['phase']) for f in r['failures']}
                          for r in outputs],
                         [{(f['field'], f['kind'], f['phase']) for f in outputs[0]['failures']}] * 3)
        return outputs

    def test_readonly_native_no_edit_agrees_with_transaction_models(self):
        outputs = self.compare_models(*self.observations(read_only=True), 'no-edit')
        self.assertTrue(all(not r['failures'] and r['blocked_edits'] == 1 for r in outputs))

    def test_disabled_native_no_edit_agrees_with_transaction_models(self):
        for read_only in (False, True):
            with self.subTest(read_only=read_only):
                self.compare_models(*self.observations(disabled=True, read_only=read_only), 'no-edit')

    def test_writable_pre_control_still_violates_readiness(self):
        outputs = self.compare_models(*self.observations(), 'violation')
        self.assertTrue(all(r['failures'][0]['kind'] == 'readiness' for r in outputs))

    def test_missing_readonly_flag_does_not_excuse_writable_control(self):
        rows, policy, explicit, contract = self.observations()
        for event in rows + explicit:
            del event['fields'][0]['readOnly']
        self.compare_models(rows, policy, explicit, contract, 'violation')

    def test_writable_control_after_hydration_has_no_readiness_failure(self):
        self.compare_models(*self.observations(phase='hydrated'), 'no-edit')

    def test_readonly_cannot_create_an_accepted_edit(self):
        rows = action_trace()
        for event in rows:
            event['fields'][0]['readOnly'] = True
        with self.assertRaisesRegex(ValueError, 'unavailable action target'):
            admit_browser_trace(rows, CONTRACT)
        result = interpret_form(rows, {'a': dict(channel='application')})
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['accepted_edits'], 0)

    def test_becoming_readonly_does_not_discharge_an_accepted_edit(self):
        rows = action_trace()
        for event in rows:
            event['phase'] = 'hydrated'
        for event in rows[3:]:
            event['fields'][0].update(readOnly=True, value='seed')
        rows[4]['body'] = json.dumps({'a': 'seed'})
        rows[-1]['payload'] = {'a': 'seed'}
        rows.insert(3, dict(type='checkpoint', phase='hydrated',
                            fields=copy.deepcopy(rows[3]['fields'])))
        self.assertEqual(admit_browser_trace(rows, CONTRACT), 1)
        native = interpret_form(rows, {'a': dict(channel='application')})
        current = interpret_transactions(rows, CONTRACT)
        reference = specify(rows, CONTRACT)
        for result in (native, current, reference):
            self.assertEqual(result['status'], 'violation')
            self.assertEqual(result['accepted_edits'], 1)
            self.assertFalse(result['unknown'])
        self.assertIn('dom-loss', {f['kind'] for f in native['failures']})
        self.assertIn('display-loss', {f['kind'] for f in current['failures']})


if __name__ == '__main__':
    unittest.main()
