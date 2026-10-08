from __future__ import annotations
import unittest,sys,pathlib,copy,itertools,json,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form,signature
from multi_explorer import pair_grid,pair_quotient,independent,representative

def fields(a='A',b='B',na=1,nb=2):
 return [{'id':'a','value':a,'node':na,'disabled':False,'readOnly':False},{'id':'b','value':b,'node':nb,'disabled':False,'readOnly':False}]
def event(typ,**kw):return dict(type=typ,phase='hydrated',fields=fields(),**kw)
def contracts():return {'a':dict(channel='application',resets=['reset'],removals=['remove']), 'b':dict(channel='application',resets=[],removals=[])}
def trace():return [event('edit',field='a',requested='A',trusted=True),event('edit',field='b',requested='B',trusted=True),event('receipt',channel='application',payload={'a':'A','b':'B'})]
class VectorOracleTests(unittest.TestCase):
 def test_boolean_is_not_number(self):
  t=trace();t[0]['fields'][0]['value']=True;t[0]['requested']=True
  for e in t[1:]:e['fields'][0]['value']=True
  t[-1]['payload']['a']=1
  self.assertEqual(interpret_form(t,contracts())['status'],'violation')
 def test_false_is_not_zero(self):
  t=trace();t[0]['fields'][0]['value']=False;t[0]['requested']=False
  for e in t[1:]:e['fields'][0]['value']=False
  t[-1]['payload']['a']=0
  self.assertEqual(interpret_form(t,contracts())['status'],'violation')
 def test_requested_type_must_match(self):
  t=trace();t[0]['fields'][0]['value']=True;t[0]['requested']=1
  self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_wrong_payload_shape(self):
  t=trace();t[-1]['payload']=[]
  self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_clean(self):self.assertEqual(interpret_form(trace(),contracts())['status'],'clean')
 def test_receiver_state_only(self):
  t=trace();t[-1]['payload']['b']='seed';r=interpret_form(t,contracts());self.assertEqual(r['failures'][0]['kind'],'state-only-loss');self.assertEqual(interpret_form(t,contracts(),ablation='dom-only')['status'],'clean')
 def test_local_reset_not_global(self):
  t=trace();t.insert(2,event('transition',name='reset',trusted=True));t[-1].update(fields=fields('seed-a','seed-b'),payload={'a':'seed-a','b':'seed-b'});r=interpret_form(t,contracts());self.assertEqual({f['field'] for f in r['failures']},{'b'});self.assertEqual(interpret_form(t,contracts(),ablation='global-reset')['status'],'clean')
 def test_new_edit_after_reset_obligates_new_epoch(self):
  t=trace();t.insert(2,event('transition',name='reset',trusted=True));t.insert(3,event('edit',field='a',requested='A',trusted=True));t[-1]['payload']['a']='seed';r=interpret_form(t,contracts());self.assertEqual(r['failures'][0]['epoch'],1)
 def test_earlier_failure_not_erased(self):
  t=trace();t.insert(2,event('checkpoint'));t[2]['fields']=fields('bad');t.insert(3,event('transition',name='reset',trusted=True));self.assertEqual(interpret_form(t,contracts())['status'],'violation')
 def test_untrusted_reset_does_not_authorize(self):
  t=trace();t.insert(2,event('transition',name='reset',trusted=False));t[-1]['payload']['a']='seed';self.assertEqual(interpret_form(t,contracts())['status'],'violation')
 def test_disabled_edit_unknown(self):
  t=trace();t[0]['fields'][0]['disabled']=True;self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_untrusted_edit_unknown(self):
  t=trace();t[0]['trusted']=False;self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_incomplete_edit_unknown(self):
  t=trace();t[0]['requested']='other';self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_missing_receipt_unknown(self):self.assertEqual(interpret_form(trace()[:-1],contracts())['status'],'inconclusive')
 def test_duplicate_receipt_unknown(self):
  t=trace();t.append(copy.deepcopy(t[-1]));self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_wrong_consumer_unknown(self):
  t=trace();t[-1]['channel']='native';self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_ambiguous_field_unknown(self):
  t=trace();t[-1]['fields'].append(copy.deepcopy(t[-1]['fields'][0]));self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_unknown_field_unknown(self):
  t=trace();t[-1]['fields'].append(dict(id='c',value='C',node=3));self.assertEqual(interpret_form(t,contracts())['status'],'inconclusive')
 def test_replacement_same_value_clean(self):
  t=trace();t[-1]['fields']=fields(na=9);self.assertEqual(interpret_form(t,contracts())['status'],'clean');self.assertEqual(interpret_form(t,contracts(),ablation='strict-node')['status'],'violation')
 def test_replacement_loss_not_forgotten(self):
  t=trace();t[-1]['fields']=fields('bad',na=9);t[-1]['payload']['a']='bad';self.assertEqual(interpret_form(t,contracts())['status'],'violation');self.assertEqual(interpret_form(t,contracts(),ablation='drop-identity')['status'],'clean')
 def test_declared_removal(self):
  t=trace();t.insert(2,event('transition',name='remove',trusted=True));t[-1]['fields']=fields()[1:];del t[-1]['payload']['a'];self.assertEqual(interpret_form(t,contracts())['status'],'clean')
 def test_removed_field_not_submitted(self):
  t=trace();t.insert(2,event('transition',name='remove',trusted=True));t[-1]['fields']=fields()[1:];self.assertEqual(interpret_form(t,contracts())['failures'][0]['kind'],'removed-field-submission')
 def test_absent_accepted_field_violation(self):
  t=trace();t[-1]['fields']=fields()[1:];self.assertEqual(interpret_form(t,contracts())['status'],'violation')
 def test_genuine_unavailability_no_edit(self):
  t=[event('edit-blocked',field='a'),event('receipt',channel='application',payload={'a':'seed','b':'seed'})];self.assertEqual(interpret_form(t,contracts())['status'],'no-edit')
 def test_readiness_truthful(self):
  t=trace();t[0]['phase']='pre';c=contracts();c['a']['unavailable_until_hydration']=True;self.assertIn('readiness',[f['kind'] for f in interpret_form(t,c)['failures']])
 def test_finite_cross_field_reset_truth_table(self):
  # Independent declarative formula versus interpreter, not browser executions.
  for permit_a,permit_b,change_a,change_b in itertools.product([False,True],repeat=4):
   c=contracts();c['a']['resets']=['reset'] if permit_a else [];c['b']['resets']=['reset'] if permit_b else []
   t=trace();t.insert(2,event('transition',name='reset',trusted=True));a='X' if change_a else 'A';b='X' if change_b else 'B';t[-1].update(fields=fields(a,b),payload={'a':a,'b':b});expected=(change_a and not permit_a) or (change_b and not permit_b)
   self.assertEqual(interpret_form(t,c)['status']=='violation',expected)
class ExplorationTests(unittest.TestCase):
 def test_reference_counts(self):self.assertEqual(len(pair_grid()),38);self.assertEqual(len(pair_quotient(True)),29);self.assertEqual(len(pair_quotient(False)),38)
 def test_idempotence_and_phase_preservation(self):
  for s in pair_grid():
   r=representative(s,True);self.assertEqual(representative(r,True),r);self.assertEqual((r.horizon,r.a,r.b),(s.horizon,s.a,s.b))
 def test_conflicts_and_top(self):
  e=json.loads((ROOT/'results/phase-grid/effects.json').read_text())['effects'];self.assertTrue(independent(e,'independent_a','independent_b'));self.assertFalse(independent(e,'coupled_a','coupled_b'));e['independent_a']['known']=False;self.assertFalse(independent(e,'independent_a','independent_b'))
 def test_parser_subset(self):
  code="""import {extract} from './scripts/extract_effects.mjs';
const cases=['(s,v)=>{s.a=v;}','(s,v)=>{s.a=s.b;}','(s,v)=>{s[v]=v;}','(s,v)=>{f(s);}','(s,v)=>{const x=s;x.a=v;}','(s,v)=>{s.a=Math.random();}','(s,v)=>{s.a+=v;}','(s,v)=>{s.a=()=>v;}'];
console.log(JSON.stringify(cases.map(x=>extract('window.HANDLERS={h:'+x+'}').h)));"""
  rs=json.loads(subprocess.check_output(['node','--input-type=module','-e',code],cwd=ROOT));self.assertEqual([r['known'] for r in rs],[True,True,False,False,False,False,False,False]);self.assertEqual(rs[1]['reads'],['state:b'])
class ParserGuardTests(unittest.TestCase):
 def check(self, source):
  code="import {extract} from './scripts/extract_effects.mjs';try {console.log(JSON.stringify(extract("+json.dumps(source)+")))} catch(e){console.log(JSON.stringify({rejected:true}))}"
  return json.loads(subprocess.check_output(['node','--input-type=module','-e',code],cwd=ROOT))
 def test_duplicate_handler_rejected(self):self.assertTrue(self.check('window.HANDLERS={x:(s,v)=>{s.a=v},x:(s,v)=>{s.b=v}}')['rejected'])
 def test_arbitrary_declaration_rejected(self):self.assertTrue(self.check('something.H={x:(s,v)=>{s.a=v}}')['rejected'])
 def test_regexp_top(self):self.assertFalse(self.check('window.HANDLERS={x:(s,v)=>{s.a=/r/}}')['x']['known'])
 def test_async_top(self):self.assertFalse(self.check('window.HANDLERS={x:async(s,v)=>{s.a=v}}')['x']['known'])
 def test_getter_rejected(self):self.assertTrue(self.check('window.HANDLERS={get x(){return 1}}')['rejected'])
 def test_prototype_handler_rejected(self):self.assertTrue(self.check('window.HANDLERS={__proto__:(s,v)=>{s.a=v}}')['rejected'])
if __name__=='__main__':unittest.main()
