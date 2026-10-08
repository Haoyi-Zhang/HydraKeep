"""Field-scoped, transaction-indexed preservation monitor.

This module does not import fixtures, browser adapters, the legacy interpreter,
source-effect hints, or the declarative specification. Inputs are observations,
not predictions. A completed finite trace needs one receipt per consumption and
coverage of its last live edit. Incomplete evidence is never a clean result.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any


def equal(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def interpret_transactions(trace: list[dict[str, Any]], contract: dict[str, Any],
                           *, ablation: str = '') -> dict[str, Any]:
    fields, consumers = contract.get('fields', {}), contract.get('consumers', {})
    if not fields or not consumers:
        raise ValueError('Nonempty fields and explicit consumers are required')
    if ablation not in ('', 'global-release', 'latest-at-receipt', 'dom-only',
                         'strict-node', 'consumer-string-coercion'):
        raise ValueError('Unknown ablation')
    for name, c in consumers.items():
        scope = c.get('fields', [])
        if (not scope or len(scope) != len(set(scope)) or not set(scope) <= set(fields)
                or not set(c.get('release_display', [])) <= set(scope)
                or not isinstance(c.get('channel'), str)):
            raise ValueError('Invalid consumer declaration: ' + str(name))
    state = {f: dict(active=False, expected=None, epoch=0, revision=0, removed=False, node=None)
             for f in fields}
    pending: dict[str, Any] = {}
    received: set[str] = set()
    covered: set[tuple] = set()
    failures, unknown = [], []
    accepted = blocked = 0

    def token(fid, st):
        return fid, st['epoch'], st['revision']

    def consumer_equal(a, b):
        if ablation != 'consumer-string-coercion':
            return equal(a, b)
        def text(value):
            if value is True: return 'true'
            if value is False: return 'false'
            if value is None: return 'null'
            return str(value)
        return text(a) == text(b)

    def fail(fid, kind, e, actual, q=None):
        q = state[fid] if q is None else q
        item = dict(field=fid, kind=kind, phase=e.get('phase'),
                    epoch=q['epoch'], revision=q['revision'], expected=q['expected'],
                    actual=actual, transaction=e.get('transaction'))
        if item not in failures:
            failures.append(item)

    for index, e in enumerate(trace):
        kind = e.get('type')
        byid = {f: [] for f in fields}
        for item in e.get('fields', []):
            fid = item.get('id')
            if fid not in byid:
                unknown.append('undeclared logical field')
            else:
                byid[fid].append(item)
        for fid, matches in byid.items():
            if len(matches) > 1:
                unknown.append('ambiguous logical field: ' + fid)
        if kind == 'transition':
            for fid, c in fields.items():
                permitted = e.get('name') in c.get('resets', [])
                permitted &= not c.get('reset_requires_user', True) or e.get('trusted') is True
                removed = e.get('name') in c.get('removals', [])
                if permitted or removed:
                    state[fid].update(active=False, epoch=state[fid]['epoch'] + 1,
                                      removed=state[fid]['removed'] or removed)
            continue  # a transition is followed by a settled observation
        if kind == 'edit-blocked':
            fs = byid.get(e.get('field'), [])
            if len(fs) != 1 or not (fs[0].get('disabled') or fs[0].get('readOnly')):
                unknown.append('unverified blocked edit')
            else:
                blocked += 1
        elif kind == 'edit':
            fid = e.get('field'); fs = byid.get(fid, [])
            if len(fs) != 1:
                unknown.append('missing or ambiguous edit target')
            elif (e.get('trusted') is not True or fs[0].get('disabled')
                  or fs[0].get('readOnly') or not equal(e.get('requested'), fs[0].get('value'))):
                unknown.append('edit lacks available completed user-action evidence')
            else:
                st = state[fid]
                st.update(active=True, expected=fs[0]['value'], removed=False, node=fs[0].get('node'),
                          revision=st['revision'] + 1)
                accepted += 1
        if kind not in ('checkpoint', 'edit', 'edit-blocked', 'consume', 'receipt'):
            continue
        for fid, c in fields.items():
            fs, st = byid[fid], state[fid]
            if len(fs) > 1:
                continue
            if (c.get('unavailable_until_hydration') and e.get('phase') == 'pre'
                    and fs and not (fs[0].get('disabled') or fs[0].get('readOnly'))):
                fail(fid, 'readiness', e, False)
            if st['active'] and fs and ablation == 'strict-node' and st.get('node') != fs[0].get('node'):
                fail(fid, 'physical-node-change', e, fs[0].get('node'))
            if st['active'] and (not fs or not equal(fs[0].get('value'), st['expected'])):
                fail(fid, 'display-loss', e, fs[0].get('value') if fs else None)
        if kind == 'consume':
            tx, name = e.get('transaction'), e.get('consumer')
            if not isinstance(tx, str) or not tx or tx in pending:
                unknown.append('missing or duplicate transaction identity'); continue
            if name not in consumers:
                unknown.append('undeclared consumer'); continue
            c = consumers[name]
            frozen = {fid: deepcopy(state[fid]) for fid in c['fields']}
            for fid, q in frozen.items():
                fs = byid[fid]
                q['visible'] = len(fs) == 1 and equal(fs[0].get('value'), q['expected'])
            pending[tx] = dict(consumer=name, frozen=frozen, index=index)
            released = set(fields) if ablation == 'global-release' else set(c.get('release_display', []))
            for fid in released:
                state[fid]['active'] = False
        elif kind == 'receipt':
            tx = e.get('transaction')
            if tx not in pending:
                unknown.append('orphan receipt'); continue
            if tx in received:
                unknown.append('duplicate receipt'); continue
            p = pending[tx]; c = consumers[p['consumer']]
            payload = e.get('payload')
            if e.get('consumer') != p['consumer'] or e.get('channel') != c['channel']:
                unknown.append('receipt consumer or channel mismatch'); continue
            if not isinstance(payload, dict):
                unknown.append('receipt payload is not an object'); continue
            received.add(tx)
            for fid, original in p['frozen'].items():
                q = state[fid] if ablation == 'latest-at-receipt' else original
                if original['active']:
                    covered.add(token(fid, original))
                if ablation == 'dom-only':
                    continue
                if q['removed'] and fid in payload:
                    fail(fid, 'removed-field-submission', e, payload[fid], q)
                elif q['active'] and (fid not in payload or not consumer_equal(payload[fid], q['expected'])):
                    visible = original['visible']
                    fail(fid, 'consumer-only-loss' if visible else 'submission-loss', e,
                         payload.get(fid), q)
    if not pending:
        unknown.append('no observed consumption')
    if set(pending) != received:
        unknown.append('missing transaction receipt')
    for fid, st in state.items():
        if st['active'] and token(fid, st) not in covered:
            unknown.append('unconsumed live edit: ' + fid)
    status = ('inconclusive' if unknown else 'violation' if failures else
              'clean' if accepted else 'no-edit')
    return dict(status=status, failures=failures, unknown=sorted(set(unknown)),
                accepted_edits=accepted, blocked_edits=blocked,
                consumptions=len(pending), receipts=len(received))


def diagnosis(out: dict[str, Any]) -> tuple:
    """Ignore timings and values, retain the semantic diagnostic identity."""
    return (out['status'], tuple(sorted({(x['field'], x['kind'], str(x['phase']),
            x['epoch'], x['revision'], str(x['transaction'])) for x in out['failures']})),
            out['accepted_edits'], out['blocked_edits'], out['consumptions'], out['receipts'])
