"""Finite adapter/runner regressions; no browsers, servers or provider APIs."""
import ast
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from transaction_oracle import diagnosis, interpret_transactions
from transaction_spec import specify

CONTRACT = dict(fields={'agree': dict(resets=['reset'], reset_requires_user=True),
                        'name': dict(resets=[])},
                consumers={'save': dict(fields=['agree'], release_display=[],
                                        channel='application')})


class TypedEditActionTests(unittest.TestCase):
    def scenario(self, name):
        module_uri = (ROOT / 'tests' / 'typed-edit-actions.mjs').as_uri()
        code = ('import {run} from ' + json.dumps(module_uri) + ';'
                'console.log(JSON.stringify(run(' + json.dumps(name) + ')));')
        observed = json.loads(subprocess.check_output(
            ['node', '--input-type=module', '-e', code], cwd=ROOT, timeout=10))
        result = interpret_transactions(observed['trace'], CONTRACT)
        return observed, result

    def assert_valid_specification(self, observed, result):
        self.assertEqual(diagnosis(result), diagnosis(specify(observed['trace'], CONTRACT)))

    def test_duplicate_check_acknowledges_noop_without_new_revision(self):
        observed, result = self.scenario('duplicate-check')
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['accepted_edits'], 1)
        self.assertEqual(observed['trace'][-1]['type'], 'edit-noop')
        self.assertFalse(observed['trace'][-1]['trusted'])
        self.assertEqual(observed['retainedEvidence'], [])
        self.assert_valid_specification(observed, result)

    def test_fresh_same_value_event_creates_new_revision(self):
        observed, result = self.scenario('fresh-same-value')
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['accepted_edits'], 2)
        self.assert_valid_specification(observed, result)

    def test_changed_value_without_new_event_is_inconclusive(self):
        _, result = self.scenario('no-new-event-changed')
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['accepted_edits'], 1)

    def test_untrusted_event_is_not_a_confirmed_noop(self):
        _, result = self.scenario('untrusted')
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['accepted_edits'], 0)

    def test_wrong_typed_value_cannot_complete(self):
        for name in ('wrong-type', 'wrong-value'):
            with self.subTest(name=name):
                _, result = self.scenario(name)
                self.assertEqual(result['status'], 'inconclusive')
                self.assertEqual(result['accepted_edits'], 0)

    def test_replaced_or_detached_node_cannot_supply_evidence(self):
        for name, accepted in (('replaced-node', 1), ('detached-event', 0)):
            with self.subTest(name=name):
                _, result = self.scenario(name)
                self.assertEqual(result['status'], 'inconclusive')
                self.assertEqual(result['accepted_edits'], accepted)

    def test_other_logical_field_cannot_supply_evidence(self):
        _, result = self.scenario('wrong-field')
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['accepted_edits'], 0)

    def test_completed_token_cannot_be_reused(self):
        observed, result = self.scenario('consumed-token')
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['accepted_edits'], 1)
        self.assertIn('completed edit action', observed['error'])

    def test_pre_action_event_is_not_fresh(self):
        _, result = self.scenario('stale-before-start')
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['accepted_edits'], 0)

    def test_reset_then_noop_does_not_reactivate_old_revision(self):
        observed, result = self.scenario('reset-and-noop')
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['accepted_edits'], 1)
        self.assert_valid_specification(observed, result)

    def test_reset_then_fresh_edit_uses_new_epoch_and_revision(self):
        observed, result = self.scenario('reset-and-fresh')
        self.assertEqual(result['status'], 'violation')
        self.assertEqual(result['accepted_edits'], 2)
        self.assertEqual([(f['epoch'], f['revision'], f['transaction'])
                          for f in result['failures']], [(1, 2, 't2')])
        self.assert_valid_specification(observed, result)

    def test_noop_does_not_hide_live_loss_before_reset(self):
        observed, result = self.scenario('noop-after-loss')
        self.assertEqual(result['status'], 'violation')
        self.assertEqual(result['accepted_edits'], 1)
        self.assertEqual([(f['kind'], f['epoch'], f['revision'])
                          for f in result['failures']], [('display-loss', 0, 1)])
        self.assert_valid_specification(observed, result)

    def test_event_sequence_does_not_depend_on_trace_array_length(self):
        observed, result = self.scenario('trace-cleared')
        self.assertEqual(result['status'], 'clean')
        completion = next(e for e in observed['trace'] if e['type'] == 'edit')
        self.assertEqual(completion['nativeSequence'], 2)
        self.assert_valid_specification(observed, result)

    def test_runner_binds_checkbox_action_before_completion(self):
        # Execute only the reviewed edit function, not the browser-study module.
        tree = ast.parse((ROOT / 'scripts' / 'run_typed_transactions.py').read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'edit')
        namespace = {'Any': object}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<owned edit function>', 'exec'),
             namespace)
        calls = []

        class Page:
            def locator(self, selector): return self
            def count(self): return 1
            def is_enabled(self): return True
            def get_attribute(self, name): return None
            def check(self): calls.append(('check', None))
            def uncheck(self): calls.append(('uncheck', None))
            def evaluate(self, source, argument):
                calls.append((source, argument))
                if 'control' in source: return 'checkbox'
                if 'beginEdit' in source: return 37

        for value, operation in ((True, 'check'), (False, 'uncheck')):
            calls.clear()
            namespace['edit'](Page(), 'agree', value)
            self.assertIn('tx.beginEdit', calls[1][0])
            self.assertEqual(calls[1][1], ['agree', value])
            self.assertEqual(calls[2][0], operation)
            self.assertIn('tx.completeEdit', calls[3][0])
            self.assertEqual(calls[3][1], 37)


if __name__ == '__main__':
    unittest.main()
