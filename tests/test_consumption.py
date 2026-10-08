import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from form_oracle import interpret_form
class ConsumptionTests(unittest.TestCase):
 def events(self):
  f=[{'id':'a','node':1,'value':'toy','disabled':False}]
  return [dict(type='edit',phase='pre',fields=f,field='a',requested='toy',trusted=True),dict(type='consume',phase='submit',fields=f),dict(type='checkpoint',phase='success',fields=[])]
 def check(self,payload,tail=()):
  return interpret_form(self.events()+list(tail)+[dict(type='receipt',phase='success',fields=[],payload=payload,channel='application')],{'a':{'channel':'application','resets':['reset']}})
 def test_success_view_does_not_lose_consumed_field(self):self.assertEqual(self.check({'a':'toy'})['status'],'clean')
 def test_stale_received_value_survives_form_removal(self):
  o=self.check({'a':'seed'});self.assertEqual(o['status'],'violation');self.assertEqual(o['failures'][0]['kind'],'state-only-loss')
 def test_reset_after_consumption_does_not_erase_pending_value(self):
  o=self.check({'a':'seed'},[dict(type='transition',name='reset',trusted=True,phase='success',fields=[])]);self.assertEqual(o['status'],'violation');self.assertEqual(o['failures'][0]['epoch'],0)
 def test_second_consumption_is_inconclusive(self):self.assertEqual(self.check({'a':'toy'},[dict(type='consume',phase='success',fields=[])])['status'],'inconclusive')
 def test_new_edit_after_consumption_is_inconclusive(self):self.assertEqual(self.check({'a':'toy'},[dict(type='edit',phase='success',fields=[],field='a')])['status'],'inconclusive')
 def test_loss_at_consumption_is_still_detected(self):
  e=self.events();e[1]['fields']=[{'id':'a','node':1,'value':'seed'}]
  o=interpret_form(e+[dict(type='receipt',phase='success',fields=[],payload={'a':'seed'},channel='application')],{'a':{'channel':'application'}})
  self.assertEqual(o['status'],'violation');self.assertEqual(o['failures'][0]['kind'],'dom-loss')
