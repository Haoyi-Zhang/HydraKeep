import unittest,sys,pathlib,itertools
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from oracle import interpret as evaluate_observations
from explorer import grid,quotient,phase_class,ACTIONS,HORIZONS

def event(typ='checkpoint',v='toy',phase='hydrated',node=1,disabled=False,**kw):
    return dict(type=typ,phase=phase,seq=0,fields=[dict(id='toy-field',node=node,value=v,attribute='seed',disabled=disabled,readOnly=False)],**kw)
def contract(**kw):
    return dict(logical_field='toy-field',initial='seed',policy='preserve-edit',channel='application-intent',**kw)
def edit(v='toy',**kw):
    return (event('native-input',v,trusted=True,eventValue=v,**kw),
            event('edit-complete',v,requested=v,**kw))

def interpret(trace, contract, **kwargs):
    # An edit fixture contains the actual native event and its completion;
    # tests below concern subsequent obligations, not fabricated edit evidence.
    observations = [e for item in trace for e in (item if isinstance(item, tuple) else (item,))]
    return evaluate_observations(observations, contract, **kwargs)
class OracleTests(unittest.TestCase):
    def test_preserved(self):
        self.assertEqual(interpret([edit(),event('application-intent',submittedValue='toy')],contract())['status'],'clean')
    def test_dom_loss(self):
        self.assertEqual(interpret([edit(),event(v='seed')],contract())['failures'][0]['kind'],'dom-loss')
    def test_state_only(self):
        r=interpret([edit(),event('application-intent',submittedValue='seed')],contract())
        self.assertEqual([f['kind'] for f in r['failures']],['state-only-loss'])
    def test_native_channel_is_not_stale_app_state(self):
        c=contract();c['channel']='native-serialization'
        self.assertEqual(interpret([edit(),event('native-serialization',serializedValue='toy',appValue='seed')],c)['status'],'clean')
    def test_authorized_epoch(self):
        self.assertEqual(interpret([edit(),event(v='seed',phase='committed')],contract(resets=['committed']))['status'],'clean')
    def test_prior_violation_survives_reset(self):
        r=interpret([edit(),event(v='seed'),event(v='seed',phase='committed')],contract(resets=['committed']))
        self.assertEqual(r['status'],'violation')
    def test_edit_after_reset_creates_obligation(self):
        r=interpret([event(v='seed',phase='committed'),edit(phase='committed'),event(v='seed',phase='committed')],contract(resets=['committed']))
        self.assertEqual(r['status'],'violation')
    def test_disabled_not_forced(self):
        c=contract(readiness='hydrated')
        r=interpret([event(phase='server-visible',disabled=True),event('edit-blocked',disabled=True)],c)
        self.assertEqual(r['status'],'no-edit')
    def test_false_readiness(self):
        self.assertEqual(interpret([event(phase='server-visible')],contract(readiness='hydrated'))['status'],'violation')
    def test_forced_edit_rejected(self):
        self.assertEqual(interpret([edit(disabled=True)],contract())['status'],'inconclusive')
    def test_identity_ambiguity(self):
        e=event();e['fields']*=2
        self.assertEqual(interpret([edit(),e],contract())['status'],'inconclusive')
    def test_replacement_retains_logical_obligation(self):
        r=interpret([edit(),event(node=2,v='seed')],contract())
        self.assertEqual(r['status'],'violation')
    def test_identity_ablations(self):
        tr=[edit(),event(node=2,v='seed')]
        self.assertEqual(interpret(tr,contract(),ablation='drop-identity')['status'],'clean')
        self.assertEqual(interpret([edit(),event(node=2)],contract(),ablation='strict-node')['status'],'violation')
    def test_attribute_is_not_value(self):
        self.assertEqual(interpret([edit()],contract())['status'],'clean')
        self.assertEqual(interpret([edit()],contract(),ablation='attribute-only')['status'],'violation')
    def test_removal_authorizes_absence_but_not_stale_submission(self):
        e=event(phase='transitioned');e['fields']=[]
        out=event('application-intent',phase='transitioned',submittedValue='seed');out['fields']=[]
        self.assertEqual(interpret([edit(),e,out],contract(remove_at='transitioned'))['failures'][0]['kind'],'removed-field-submission')
    def test_typed_values(self):
        for v in ['toy',True,False,'B']:
            self.assertEqual(interpret([edit(v),event('application-intent',v,submittedValue=v)],contract())['status'],'clean')
    def test_untrusted_reset_does_not_discharge(self):
        tr=[edit(),event('user-reset',trusted=False),event(v='seed',phase='transitioned')]
        self.assertEqual(interpret(tr,contract(resets=['transitioned'],reset_requires_user=True))['status'],'violation')
    def test_trusted_reset_discharges(self):
        tr=[edit(),event('user-reset',trusted=True),event(v='seed',phase='transitioned')]
        self.assertEqual(interpret(tr,contract(resets=['transitioned'],reset_requires_user=True))['status'],'clean')
    def test_missing_consumer_is_inconclusive(self):
        self.assertEqual(interpret([edit(),event('native-serialization',serializedValue='toy')],contract())['status'],'inconclusive')
    def test_wrong_logical_field_is_inconclusive(self):
        e=event();e['fields'][0]['id']='other'
        self.assertEqual(interpret([edit(),e],contract())['status'],'inconclusive')
    def test_grid_partition(self):
        self.assertEqual(len(grid()),18);self.assertEqual(len(quotient()),9)
        self.assertEqual(set(map(phase_class,grid())),set(map(phase_class,quotient())))
    def test_finite_congruence(self):
        # Exhaust all choices of preservation/overwrite for H,C,T, initial readiness,
        # application synchronization, and permitted-reset subsets. Independent toy model.
        tested=0
        for overwrites in itertools.product([False,True],repeat=3):
            for blocked,stale in itertools.product([False,True],repeat=2):
                for reset_bits in itertools.product([False,True],repeat=3):
                    outcomes={}
                    for s in grid():
                        value=0;expected=None;enabled=not blocked;viol=False;phase=0
                        for i in range(HORIZONS[s.horizon]+1):
                            if i==s.gap and enabled:value=1;expected=1
                            if i==HORIZONS[s.horizon]:break
                            a=ACTIONS[i]
                            if a in ['hydrate','commit','transition']:
                                if overwrites[phase]:value=0
                                if reset_bits[phase]:expected=None
                                if expected is not None and value!=expected:viol=True
                                phase+=1;enabled=True
                        if expected is not None and (0 if stale else value)!=expected:viol=True
                        sig=(viol,expected is not None)
                        key=phase_class(s)
                        if key in outcomes:self.assertEqual(sig,outcomes[key])
                        outcomes[key]=sig;tested+=1
        self.assertEqual(tested,4608)
if __name__=='__main__':unittest.main()
