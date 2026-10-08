"""Independent contract interpreter. No imports from browser fixtures/adapters.
Only typed observation events and an externally declared field contract are read.
"""
from __future__ import annotations
from typing import Any

def same_value(a:Any,b:Any)->bool:
    """JSON value equality must not equate Boolean true/false with numbers 1/0."""
    return type(a) is type(b) and a==b


def interpret(trace: list[dict[str, Any]], contract: dict[str, Any], *, ablation: str = '') -> dict[str, Any]:
    expected=None; active=False; first_node=None; removed=False; blocked=0; accepted=0
    failures=[]; inconclusive=[]; intentional=0; reset_seen=set()
    user_reset_seen=False; channel_seen=False; submit_seen=False
    def failure(kind,event,actual):
        key=(kind,event.get('phase'))
        if not any((x['kind'],x['phase'])==key for x in failures):
            failures.append({'kind':kind,'phase':event.get('phase'),'seq':event.get('seq'),'expected':expected,'actual':actual})
    for e in trace:
        typ=e.get('type'); phase=e.get('phase'); fields=e.get('fields',[])
        if typ=='user-reset' and e.get('trusted') is True:user_reset_seen=True
        if typ=='native-serialization':submit_seen=True
        if any(f.get('id')!=contract['logical_field'] for f in fields):
            inconclusive.append('observed field does not match declared logical identity');continue
        if typ=='edit-blocked':blocked+=1;continue
        if typ=='edit-absent':continue
        if typ=='edit-complete':
            if len(fields)!=1:
                inconclusive.append('ambiguous edit identity' if len(fields)>1 else 'missing edited field');continue
            if fields[0].get('disabled') or fields[0].get('readOnly'):
                inconclusive.append('an edit was reported on an unavailable field');continue
            if not same_value(e.get('requested'),fields[0]['value']):
                inconclusive.append('requested edit did not complete');continue
            expected=fields[0]['value'];active=True;first_node=fields[0]['node'];accepted+=1
        if typ not in ['checkpoint','edit-complete','application-intent','native-serialization','application-submitted']:
            continue
        # Only explicit transition-completion checkpoints open a new policy epoch.
        if (typ=='checkpoint' and phase in contract.get('resets',[]) and phase not in reset_seen
            and (not contract.get('reset_requires_user',False) or user_reset_seen)):
            if active and fields and not same_value(fields[0]['value'],expected):intentional+=1
            expected=contract['initial'];active=False;reset_seen.add(phase)
        if typ=='checkpoint' and phase==contract.get('remove_at'):
            removed=True;active=False
        if len(fields)>1:
            inconclusive.append('ambiguous logical field identity');continue
        if contract.get('readiness') and phase in ['server-visible','loaded'] and fields and not fields[0]['disabled']:
            failure('readiness',e,False)
        if active:
            if not fields:
                failure('dom-loss',e,None)
            else:
                if first_node!=fields[0]['node']:
                    if ablation=='drop-identity':active=False;continue
                    if ablation=='strict-node':failure('node-change',e,fields[0]['value'])
                actual=fields[0]['value']
                if ablation=='attribute-only':actual=fields[0].get('attribute')
                if not same_value(actual,expected):failure('dom-loss',e,actual)
        channel=contract.get('channel','application-intent')
        is_channel=typ==channel or (channel=='application-intent' and typ=='application-submitted')
        if is_channel:
            channel_seen=True
            actual=e.get('submittedValue') if typ.startswith('application') else e.get('serializedValue')
            if removed:
                if actual is not None:failure('removed-field-submission',e,actual)
            elif active and not same_value(actual,expected):
                visible=bool(fields) and same_value(fields[0]['value'],expected)
                failure('state-only-loss' if visible else 'submission-loss',e,actual)
    if submit_seen and not channel_seen:
        inconclusive.append('declared submission channel was not observed')
    # A valid zero-edit run is a readiness/absence control, not a preservation success.
    status='inconclusive' if inconclusive else 'violation' if failures else 'clean' if accepted else 'no-edit'
    return {'status':status,'failures':failures,'inconclusive':sorted(set(inconclusive)),
            'accepted_edits':accepted,'blocked_edits':blocked,'intentional_replacements':intentional}
