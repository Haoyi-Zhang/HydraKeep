"""Finite synthetic gate tests, not browser observations."""
import sys, pathlib, unittest, copy
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from validation import validate_pair_runs
from multi_explorer import pair_grid, pair_quotient

class ValidationTests(unittest.TestCase):
    def fixture(self):
        def row(s, rep):
            return {'case':'unit', 'rep':rep, 'schedule':s.as_dict(), 'source_independent':True,
                    'oracle':{'status':'clean', 'failures':[], 'accepted_edits':2, 'blocked_edits':0}}
        return ([row(s,r) for r in range(2) for s in pair_grid()],
                [row(s,0) for s in pair_quotient(True)])
    def test_complete_agreement(self):
        g,q=self.fixture();self.assertEqual(validate_pair_runs(g,q,{'unit':True})['omitted_comparisons'],9)
    def test_missing_and_duplicate_schedules_rejected(self):
        g,q=self.fixture()
        for bad in [g[:-1],g+[copy.deepcopy(g[0])]]:
            with self.assertRaises(ValueError):validate_pair_runs(bad,q,{'unit':True})
    def test_same_status_different_diagnosis_rejected(self):
        g,q=self.fixture();g[1]['oracle']['failures']=[{'field':'b','kind':'state-only-loss','phase':'hydrated','epoch':0}]
        with self.assertRaisesRegex(ValueError,'within-class'):validate_pair_runs(g,q,{'unit':True})
    def test_replay_and_repeat_disagreement_rejected(self):
        g,q=self.fixture();q[0]['oracle']['accepted_edits']=1
        with self.assertRaisesRegex(ValueError,'replay'):validate_pair_runs(g,q,{'unit':True})
        g,q=self.fixture();g[-1]['oracle']['blocked_edits']=1
        with self.assertRaisesRegex(ValueError,'repeated'):validate_pair_runs(g,q,{'unit':True})
    def test_stale_source_flags_rejected(self):
        g,q=self.fixture()
        with self.assertRaisesRegex(ValueError,'source proposal'):validate_pair_runs(g,q,{'unit':False})
