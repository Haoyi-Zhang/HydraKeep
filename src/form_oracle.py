"""Vector, epoch-aware preservation interpreter; no fixture or framework imports.

Contract policies are external. Observations can be incomplete: absence of a
receipt, ambiguous identity, or a non-user edit is inconclusive rather than clean.
"""
from __future__ import annotations
from typing import Any

def same_value(a:Any,b:Any)->bool:
    """JSON value equality must not equate Boolean true/false with numbers 1/0."""
    return type(a) is type(b) and a==b


def interpret_form(trace:list[dict[str,Any]], contracts:dict[str,dict[str,Any]], *, ablation:str='')->dict[str,Any]:
    state={k:{'active':False,'expected':None,'node':None,'epoch':0,'removed':False,'seen':False} for k in contracts}
    failures=[];unknown=[];accepted=0;blocked=0;receipts=0;pending=None
    def fail(fid,kind,e,actual,obligation=None):
        q=state[fid] if obligation is None else obligation
        item={'field':fid,'kind':kind,'phase':e.get('phase'),'epoch':q['epoch'],'expected':q['expected'],'actual':actual}
        if item not in failures:failures.append(item)
    for e in trace:
        typ=e.get('type');phase=e.get('phase');byid={k:[] for k in contracts}
        for f in e.get('fields',[]):
            if f['id'] in byid:byid[f['id']].append(f)
            else:unknown.append('undeclared logical identity: '+f['id'])
        if typ=='transition':
            for fid,c in contracts.items():
                permit=e.get('name') in c.get('resets',[]) and (not c.get('reset_requires_user',True) or e.get('trusted') is True)
                if ablation=='global-reset' and e.get('name')=='reset' and e.get('trusted') is True:permit=True
                if permit:state[fid].update(active=False,epoch=state[fid]['epoch']+1)
                if e.get('name') in c.get('removals',[]):state[fid].update(active=False,removed=True,epoch=state[fid]['epoch']+1)
        if typ=='edit-blocked':blocked+=1
        if typ=='edit':
            if pending is not None:
                unknown.append('edit after terminal consumption is outside the profile');continue
            fid=e.get('field'); fs=byid.get(fid,[])
            if len(fs)!=1:unknown.append('ambiguous or missing edit field');continue
            f=fs[0]
            if f.get('disabled') or f.get('readOnly') or e.get('trusted') is not True:
                unknown.append('edit lacks genuine available-control evidence');continue
            if not same_value(e.get('requested'),f['value']):unknown.append('edit did not complete');continue
            state[fid].update(active=True,expected=f['value'],node=f['node'],seen=True,removed=False);accepted+=1
        if typ=='consume':
            if pending is not None:unknown.append('multiple terminal consumptions are outside the profile')
            else:pending={fid:{**st,'visible':len(byid[fid])==1 and same_value(byid[fid][0]['value'],st['expected'])} for fid,st in state.items()}
        if typ not in ['checkpoint','edit','consume','receipt']:continue
        for fid,c in contracts.items():
            st=state[fid];fs=byid[fid]
            if len(fs)>1:unknown.append('ambiguous logical identity: '+fid);continue
            if c.get('unavailable_until_hydration') and phase=='pre' and fs and not fs[0].get('disabled'):
                fail(fid,'readiness',e,False)
            if st['active'] and (pending is None or typ=='consume'):
                if not fs:fail(fid,'dom-loss',e,None)
                else:
                    if st['node']!=fs[0]['node']:
                        if ablation=='drop-identity':st['active']=False;continue
                        if ablation=='strict-node':fail(fid,'node-change',e,fs[0]['value'])
                    if not same_value(fs[0]['value'],st['expected']):fail(fid,'dom-loss',e,fs[0]['value'])
            if typ=='receipt':
                if e.get('channel')!=c['channel']:unknown.append('wrong consumer channel: '+fid);continue
                payload=e.get('payload',{})
                if not isinstance(payload,dict):unknown.append('invalid consumer payload shape');continue
                q=pending[fid] if pending is not None else st
                if q['removed'] and fid in payload and ablation!='dom-only':fail(fid,'removed-field-submission',e,payload[fid],q)
                elif q['active'] and ablation!='dom-only' and not same_value(payload.get(fid),q['expected']):
                    visible=q['visible'] if pending is not None else len(fs)==1 and same_value(fs[0]['value'],q['expected'])
                    fail(fid,'state-only-loss' if visible else 'submission-loss',e,payload.get(fid),q)
        if typ=='receipt':receipts+=1
    if receipts!=1:unknown.append('exactly one observed receipt is required')
    status='inconclusive' if unknown else 'violation' if failures else 'clean' if accepted else 'no-edit'
    return {'status':status,'failures':failures,'unknown':sorted(set(unknown)),'accepted_edits':accepted,'blocked_edits':blocked,'receipts':receipts}

def signature(out:dict[str,Any]):
    return (out['status'],tuple(sorted({(f['field'],f['kind'],f['phase'],f['epoch']) for f in out['failures']})),out['accepted_edits'],out['blocked_edits'])
