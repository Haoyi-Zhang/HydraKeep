"""Slow prefix specification for WELL-FORMED transaction traces.

Unlike the implementation, each observation is interpreted from its entire event
prefix and each receipt independently finds its matching consumption. The test
generator supplies valid identities and user actions. Protocol rejection is tested
separately; this specification is not an alternate evidence validator.
"""
from __future__ import annotations
from typing import Any


def obligation(prefix: list[dict], field: str, contract: dict) -> dict:
    policy = contract['fields'][field]
    resets = [i for i, e in enumerate(prefix) if e['type'] == 'transition' and
              ((e.get('name') in policy.get('resets', []) and
                (not policy.get('reset_requires_user', True) or e.get('trusted') is True))
               or e.get('name') in policy.get('removals', []))]
    edits = [i for i, e in enumerate(prefix) if e['type'] == 'edit' and e['field'] == field]
    releases = [i for i, e in enumerate(prefix) if e['type'] == 'consume' and
                field in contract['consumers'][e['consumer']].get('release_display', [])]
    last_edit = max(edits, default=-1)
    last_reset = max(resets, default=-1)
    last_release = max(releases, default=-1)
    expected = prefix[last_edit]['requested'] if edits else None
    removals = [i for i, e in enumerate(prefix) if e['type'] == 'transition'
                and e.get('name') in policy.get('removals', [])]
    removed = max(removals, default=-1) > last_edit
    return dict(active=last_edit > max(last_reset, last_release), expected=expected,
                epoch=len(resets), revision=len(edits), removed=removed)


def matches(a: Any, b: Any) -> bool:
    return type(a) == type(b) and a == b


def specify(trace: list[dict], contract: dict) -> dict:
    failures = []
    consumption = {e['transaction']: i for i, e in enumerate(trace) if e['type'] == 'consume'}
    receipts = {e['transaction']: e for e in trace if e['type'] == 'receipt'}
    covered = set()

    def record(fid, kind, event, q, actual):
        f = dict(field=fid, kind=kind, phase=event.get('phase'), epoch=q['epoch'],
                 revision=q['revision'], expected=q['expected'], actual=actual,
                 transaction=event.get('transaction'))
        if f not in failures:
            failures.append(f)

    for i, e in enumerate(trace):
        if e['type'] not in ('checkpoint', 'edit', 'edit-blocked', 'consume', 'receipt'):
            continue
        # The current edit has completed; the current consume has not released yet.
        prefix = trace[:i+1] if e['type'] == 'edit' else trace[:i]
        visible = {f['id']: f['value'] for f in e.get('fields', [])}
        for fid in contract['fields']:
            q = obligation(prefix, fid, contract)
            if q['active'] and (fid not in visible or not matches(visible[fid], q['expected'])):
                record(fid, 'display-loss', e, q, visible.get(fid))
            policy = contract['fields'][fid]
            nodes = [f for f in e.get('fields', []) if f['id'] == fid]
            if (policy.get('unavailable_until_hydration') and e.get('phase') == 'pre' and
                nodes and not(nodes[0].get('disabled') or nodes[0].get('readOnly'))):
                record(fid, 'readiness', e, q, False)
        if e['type'] == 'receipt':
            j = consumption[e['transaction']]
            start = trace[j]
            consumer = contract['consumers'][start['consumer']]
            at_start = {f['id']: f['value'] for f in start.get('fields', [])}
            for fid in consumer['fields']:
                q = obligation(trace[:j], fid, contract)
                if q['active']:
                    covered.add((fid, q['epoch'], q['revision']))
                if q['removed'] and fid in e['payload']:
                    record(fid, 'removed-field-submission', e, q, e['payload'][fid])
                elif q['active'] and (fid not in e['payload'] or not matches(e['payload'][fid], q['expected'])):
                    good_display = fid in at_start and matches(at_start[fid], q['expected'])
                    record(fid, 'consumer-only-loss' if good_display else 'submission-loss',
                           e, q, e['payload'].get(fid))
    unknown = []
    if not consumption:
        unknown.append('no observed consumption')
    if consumption.keys() != receipts.keys():
        unknown.append('missing transaction receipt')
    for fid in contract['fields']:
        q = obligation(trace, fid, contract)
        if q['active'] and (fid, q['epoch'], q['revision']) not in covered:
            unknown.append('unconsumed live edit: ' + fid)
    accepted = sum(e['type'] == 'edit' for e in trace)
    return dict(status='inconclusive' if unknown else 'violation' if failures else 'clean' if accepted else 'no-edit',
                failures=failures, unknown=sorted(unknown), accepted_edits=accepted,
                blocked_edits=sum(e['type'] == 'edit-blocked' for e in trace),
                consumptions=len(consumption), receipts=len(receipts))
