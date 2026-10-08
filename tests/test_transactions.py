import copy
import itertools
import json
import pathlib
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from transaction_oracle import interpret_transactions, diagnosis
from transaction_spec import specify


def contract(scope='both', release=False, reset='a'):
    fs = ['a', 'b'] if scope == 'both' else [scope]
    return dict(fields={f:dict(resets=['reset'] if reset == f else [], removals=[],
                              reset_requires_user=True) for f in ['a','b']},
                consumers={'save':dict(fields=fs, release_display=fs if release else [], channel='application'),
                           'all':dict(fields=['a','b'], release_display=[], channel='application')})


def event(kind, a='a1', b='b1', **extra):
    return dict(type=kind, phase=extra.pop('phase','hydrated'),
                fields=[dict(id=f,value=v,node=f+'-node',disabled=False,readOnly=False)
                        for f,v in [('a',a),('b',b)] if v is not None], **extra)


def edit(f, a='a1', b='b1'):
    return event('edit', a, b, field=f, requested=a if f == 'a' else b, trusted=True)


def consume(tx='t1', consumer='all', a='a1', b='b1'):
    return event('consume', a,b, transaction=tx, consumer=consumer)


def receipt(tx='t1', consumer='all', a='a1', b='b1', payload=None):
    return event('receipt',a,b,transaction=tx,consumer=consumer,channel='application',
                 payload={'a':a,'b':b} if payload is None else payload)


def generated_traces():
    # 3 scopes x 2 terminal policies x 3 reset scopes x 2 reset placements x
    # 2 revised fields x 2 receipt orders x 4 payload variants x 2 display variants.
    for scope, release, reset, do_reset, revised, reversed_ack, corrupt, lost in itertools.product(
            ['a','b','both'], [False,True], ['a','b','none'], [False,True],
            ['a','b'], [False,True], range(4), [False,True]):
        c = contract(scope,release,reset)
        t = [edit('a',b='seed-b'),edit('b'),consume(consumer='save')]
        a,b = 'a1','b1'
        if do_reset:
            t.append(event('transition',a,b,name='reset',trusted=True))
            if reset == 'a': a='seed-a'
            if reset == 'b': b='seed-b'
        if revised == 'a': a='a2'
        else: b='b2'
        t.append(edit(revised,a,b))
        if lost:
            # A later undesired overwrite, not a failed typing action.
            a='lost-a'
        t.extend([event('checkpoint',a,b),consume('t2','all',a,b)])
        p1 = {f: f+'1' for f in c['consumers']['save']['fields']}
        p2 = {'a':a,'b':b}
        if corrupt == 1: p1={f:'stale' for f in p1}
        if corrupt == 2: p2['b']='stale'
        if corrupt == 3: p1={}
        rs = [receipt('t1','save',a,b,p1),receipt('t2','all',a,b,p2)]
        t.extend(reversed(rs) if reversed_ack else rs)
        yield c,t


class TransactionTests(unittest.TestCase):
    def test_removal_survives_reset_until_accepted_edit(self):
        c = contract()
        c['fields']['a']['removals'] = ['remove']
        prefix = [edit('a'), event('transition', name='remove', trusted=True),
                  event('checkpoint', a=None), event('transition', a=None, name='reset', trusted=True),
                  event('checkpoint', a=None)]
        for payload, expected in [({'a': 'stale', 'b': 'b1'}, 'violation'), ({'b': 'b1'}, 'clean')]:
            trace = prefix + [consume(a=None), receipt(a=None, payload=payload)]
            actual, specified = interpret_transactions(trace, c), specify(trace, c)
            self.assertEqual(actual['status'], expected)
            self.assertEqual(diagnosis(actual), diagnosis(specified))
        trace = prefix + [edit('a', a='new'), consume(a='new'), receipt(a='new')]
        self.assertEqual(interpret_transactions(trace, c)['status'], 'clean')
        self.assertEqual(diagnosis(interpret_transactions(trace, c)), diagnosis(specify(trace, c)))

    def test_bounded_differential(self):
        count=0
        for c,t in generated_traces():
            actual,expected=interpret_transactions(t,c),specify(t,c)
            self.assertEqual(diagnosis(actual),diagnosis(expected),(c,t,actual,expected))
            count+=1
        self.assertEqual(count,1152)

    def test_correct_out_of_order_receipts(self):
        t=[edit('a'),consume(),edit('a','a2'),consume('t2',a='a2'),
           receipt('t2',a='a2'),receipt(a='a2',payload={'a':'a1','b':'b1'})]
        self.assertEqual(interpret_transactions(t,contract())['status'],'clean')
        self.assertEqual(interpret_transactions(t,contract(),ablation='latest-at-receipt')['status'],'violation')

    def test_late_read_uses_old_consumption(self):
        t=[edit('a'),consume(),edit('a','a2'),consume('t2',a='a2'),
           receipt('t2',a='a2'),receipt(a='a2')]
        result=interpret_transactions(t,contract())
        self.assertEqual(result['status'],'violation')
        self.assertEqual(result['failures'][0]['transaction'],'t1')

    def test_scope_does_not_release_other_field(self):
        c=contract('a',True)
        t=[edit('a',b='seed-b'),edit('b'),consume(consumer='save'),
           event('checkpoint',None,'bad-b'),consume('t2','all',None,'bad-b'),
           receipt('t1','save',None,'bad-b',{'a':'a1'}),receipt('t2','all',None,'bad-b',{'b':'bad-b'})]
        self.assertEqual(interpret_transactions(t,c)['status'],'violation')
        self.assertEqual(interpret_transactions(t,c,ablation='global-release')['status'],'clean')

    def test_reset_does_not_cancel_frozen_request(self):
        t=[edit('a'),consume(),event('transition',name='reset',trusted=True),
           receipt(a='seed-a',payload={'a':'wrong','b':'b1'})]
        r=interpret_transactions(t,contract())
        self.assertEqual(r['status'],'violation')
        self.assertEqual(r['failures'][0]['expected'],'a1')

    def test_terminal_removal_is_clean(self):
        c=contract('both',True)
        t=[edit('a'),consume(consumer='save'),receipt(consumer='save',a=None,b=None,payload={'a':'a1','b':'b1'})]
        self.assertEqual(interpret_transactions(t,c)['status'],'clean')

    def test_orphan_receipt(self):
        self.assertEqual(interpret_transactions([receipt()],contract())['status'],'inconclusive')

    def test_duplicate_receipt(self):
        self.assertEqual(interpret_transactions([edit('a'),consume(),receipt(),receipt()],contract())['status'],'inconclusive')

    def test_duplicate_consume_identity(self):
        self.assertEqual(interpret_transactions([edit('a'),consume(),consume(),receipt()],contract())['status'],'inconclusive')

    def test_missing_receipt(self):
        self.assertEqual(interpret_transactions([edit('a'),consume()],contract())['status'],'inconclusive')

    def test_wrong_channel(self):
        r=receipt();r['channel']='native'
        self.assertEqual(interpret_transactions([edit('a'),consume(),r],contract())['status'],'inconclusive')

    def test_wrong_consumer(self):
        r=receipt();r['consumer']='save'
        self.assertEqual(interpret_transactions([edit('a'),consume(),r],contract())['status'],'inconclusive')

    def test_unconsumed_new_edit(self):
        t=[edit('a'),consume(),receipt(),edit('a','a2')]
        self.assertEqual(interpret_transactions(t,contract())['status'],'inconclusive')

    def test_ambiguous_identity(self):
        e=edit('a');e['fields'].append(copy.deepcopy(e['fields'][0]))
        self.assertEqual(interpret_transactions([e,consume(),receipt()],contract())['status'],'inconclusive')

    def test_forced_or_partial_edit(self):
        for field,value in [('trusted',False),('requested','unfinished')]:
            e=edit('a');e[field]=value
            self.assertEqual(interpret_transactions([e,consume(),receipt()],contract())['status'],'inconclusive')

    def test_typed_equality(self):
        t=[edit('a',True),consume(a=True),receipt(a=True,payload={'a':1,'b':'b1'})]
        self.assertEqual(interpret_transactions(t,contract())['status'],'violation')

    def test_consumer_string_coercion_ablation(self):
        t=[edit('a',True),consume(a=True),
           receipt(a=True,payload={'a':'true','b':'b1'})]
        self.assertEqual(interpret_transactions(t,contract())['status'],'violation')
        self.assertEqual(interpret_transactions(
            t,contract(),ablation='consumer-string-coercion')['status'],'clean')

    def test_strict_physical_node_ablation(self):
        checkpoint=event('checkpoint')
        checkpoint['fields'][0]['node']='replacement-node'
        t=[edit('a'),checkpoint,consume(),receipt()]
        self.assertEqual(interpret_transactions(t,contract())['status'],'clean')
        strict=interpret_transactions(t,contract(),ablation='strict-node')
        self.assertEqual(strict['status'],'violation')
        self.assertTrue(any(failure['kind']=='physical-node-change'
                            for failure in strict['failures']))

    def test_blocked_evidence(self):
        e=event('edit-blocked',field='a')
        self.assertEqual(interpret_transactions([e,consume(),receipt()],contract())['status'],'inconclusive')
        e['fields'][0]['disabled']=True
        self.assertEqual(interpret_transactions([e,consume(),receipt()],contract())['status'],'no-edit')

    def test_invalid_consumer_scope(self):
        c=contract('a');c['consumers']['save']['release_display']=['b']
        with self.assertRaises(ValueError):interpret_transactions([],c)

    def test_prefix_failure_not_erased_by_reset(self):
        t=[edit('a'),event('checkpoint','wrong'),event('transition',name='reset',trusted=True),
           consume(a='seed-a'),receipt(a='seed-a')]
        self.assertEqual(interpret_transactions(t,contract())['status'],'violation')


if __name__=='__main__': unittest.main()
