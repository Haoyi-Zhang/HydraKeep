import copy
import unittest
from oracle import interpret
from test_oracle import event, contract
from form_oracle import interpret_form


class EditEvidenceTests(unittest.TestCase):
    def observed(self):
        return [event('native-input', trusted=True, eventValue='toy'),
                event('edit-complete', requested='toy'),
                event('application-intent', submittedValue='toy')]

    def test_missing_or_untrusted_native_edit_is_inconclusive(self):
        rows = self.observed()
        self.assertEqual(interpret(rows, contract())['status'], 'clean')
        self.assertEqual(interpret(rows[1:], contract())['status'], 'inconclusive')
        rows[0]['trusted'] = False
        self.assertEqual(interpret(rows, contract())['status'], 'inconclusive')

    def test_wrong_target_and_value_are_not_accepted(self):
        for change in ('node', 'value', 'field'):
            rows = self.observed()
            if change == 'node': rows[0]['fields'][0]['node'] = 4
            if change == 'value': rows[0]['eventValue'] = 'other'
            if change == 'field': rows[0]['fields'][0]['id'] = 'other'
            self.assertEqual(interpret(rows, contract())['status'], 'inconclusive')

    def test_native_evidence_cannot_be_reused(self):
        rows = self.observed()
        rows.insert(2, copy.deepcopy(rows[1]))
        result = interpret(rows, contract())
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['accepted_edits'], 1)

    def test_dom_only_omits_removed_payload_check(self):
        control = dict(id='a', node=1, value='toy', disabled=False, readOnly=False)
        rows = [dict(type='edit', field='a', trusted=True, requested='toy', fields=[control]),
                dict(type='transition', name='remove', fields=[]),
                dict(type='consume', fields=[]),
                dict(type='receipt', channel='application', payload={'a': 'toy'}, fields=[])]
        contracts = {'a': dict(channel='application', removals=['remove'])}
        self.assertEqual(interpret_form(rows, contracts)['status'], 'violation')
        self.assertEqual(interpret_form(rows, contracts, ablation='dom-only')['status'], 'clean')
