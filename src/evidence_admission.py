"""Browser evidence admission, separate from the conditional semantic models.

Reject incomplete provenance; never reconstruct absent events from an edit's
trust flag. This checks internal bindings, not the honesty of a compromised
observer. Positions in the retained event list, not wall-clock timestamps,
define causal order.
"""
from __future__ import annotations


def require(condition, message):
    if not condition:
        raise ValueError('Evidence admission: ' + message)


def typed_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def admit_edits(trace, fields):
    """Bind each completed scalar edit to one fresh available-target action.

    Partial typing events may carry intermediate values. The native sequence
    cited by the completion must be the last event of that action, and its
    value must equal both the request and the completed live value. Confirmed
    no-ops create no revision and require no native event.
    """
    active = None
    actions = set()
    last_sequence = 0
    edits = 0
    for event in trace:
        matches = {}
        for item in event.get('fields', []):
            fid = item.get('id')
            require(fid in fields and fid not in matches, 'undeclared or duplicate field')
            matches[fid] = item
        kind = event.get('type')
        if kind not in ('edit-start', 'native-input', 'native-change', 'edit', 'edit-noop'):
            continue
        fid = event.get('field')
        require(fid in fields and fid in matches, 'missing action target')
        target = matches[fid]
        require(type(target.get('node')) is int and target['node'] > 0,
                'physical node must be a positive integer')
        if kind == 'edit-start':
            action = event.get('action')
            require(type(action) is int and action > 0 and action not in actions
                    and active is None, 'missing, overlapping or reused action')
            require(typed_equal(event.get('node'), target['node'])
                    and target.get('disabled') is False and target.get('readOnly') is False,
                    'unavailable action target')
            require(type(event.get('requested')) in (str, bool), 'unsupported requested type')
            actions.add(action)
            active = dict(action=action, field=fid, node=target['node'],
                          before=target.get('value'), requested=event['requested'], native=None)
        elif kind in ('native-input', 'native-change'):
            seq = event.get('sequence')
            require(type(seq) is int and seq > last_sequence, 'missing or stale native sequence')
            last_sequence = seq
            require('eventValue' in event and typed_equal(event.get('node'), target['node'])
                    and typed_equal(event['eventValue'], target.get('value')),
                    'native value or physical target differs from snapshot')
            # The observer binds every native event for the active logical field.
            # A missing binding must not hide a newer event from completion.
            if ((active is not None and fid == active['field'])
                    or event.get('action') is not None):
                require(type(event.get('action')) is int and active is not None
                        and event['action'] == active['action'] and fid == active['field']
                        and typed_equal(target['node'], active['node']),
                        'native event belongs to another action or target')
                require(event.get('trusted') is True, 'untrusted native action event')
                active['native'] = event
        else:
            require(type(event.get('action')) is int and active is not None
                    and event['action'] == active['action'] and fid == active['field']
                    and typed_equal(target['node'], active['node']),
                    'completion lacks a fresh matching action')
            require(target.get('disabled') is False and target.get('readOnly') is False
                    and typed_equal(event.get('requested'), active['requested'])
                    and typed_equal(target.get('value'), active['requested']),
                    'completion value or availability differs')
            native = active['native']
            if kind == 'edit-noop':
                require(native is None and event.get('nativeSequence') is None
                        and event.get('trusted') is False
                        and typed_equal(active['before'], active['requested']),
                        'unverified no-op')
            else:
                require(native is not None and event.get('trusted') is True
                        and type(event.get('nativeSequence')) is int
                        and event.get('nativeSequence') == native['sequence']
                        and typed_equal(native['eventValue'], active['requested']),
                        'completion lacks matching trusted native value')
                edits += 1
            active = None
    require(active is None, 'unfinished action')
    return edits


def admit_transactions(trace, contract):
    """Enforce consume < dispatch < acknowledgment < receipt for every ID.

    Different transaction receipt orders remain valid. Order is checked within
    each transaction; no sorting or inferred commitment is inserted.
    """
    stages = {}
    for event in trace:
        kind = event.get('type')
        if kind not in ('consume', 'dispatch', 'ack', 'receipt'):
            continue
        tx, consumer = event.get('transaction'), event.get('consumer')
        require(isinstance(tx, str) and bool(tx), 'missing transaction identity')
        require(consumer in contract['consumers'], 'undeclared consumer')
        previous, owner = stages.get(tx, (None, None))
        expected = {'consume': None, 'dispatch': 'consume', 'ack': 'dispatch', 'receipt': 'ack'}[kind]
        require(previous == expected and (owner is None or owner == consumer),
                'duplicate, inverted or mismatched transaction event')
        if kind == 'receipt':
            require(event.get('channel') == contract['consumers'][consumer]['channel'],
                    'receipt channel differs')
        stages[tx] = (kind, consumer)
    require(bool(stages) and all(stage == 'receipt' for stage, _ in stages.values()),
            'incomplete transaction chain')


def admit_browser_trace(trace, contract):
    count = admit_edits(trace, contract['fields'])
    admit_transactions(trace, contract)
    return count
