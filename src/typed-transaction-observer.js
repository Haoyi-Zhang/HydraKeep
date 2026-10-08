/* Observation and loopback transport for heterogeneous form controls.
   The adapter records typed live values; it never decides contract correctness. */
(() => {
  const ids = new WeakMap(); let serial = 0, eventSequence = 0, actionSequence = 0;
  let editAction = null;
  const nodeOf = el => {
    if (!ids.has(el)) ids.set(el, ++serial);
    return ids.get(el);
  };
  const sameValue = (a, b) => Object.is(a, b) ||
    (Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
     a.every((value, index) => Object.is(value, b[index])));
  const valueOf = el => {
    if (el instanceof HTMLInputElement && el.type === 'checkbox') return el.checked;
    if (el instanceof HTMLSelectElement && el.multiple)
      return [...el.selectedOptions].map(option => option.value);
    return el.value;
  };
  const kindOf = el => el instanceof HTMLSelectElement ? (el.multiple ? 'select-multiple' : 'select-one')
    : el instanceof HTMLTextAreaElement ? 'textarea'
    : el instanceof HTMLInputElement ? el.type : el.tagName.toLowerCase();
  const tx = window.tx = {trace: [], phase: 'pre', count: 0, pending: new Map(), last: {}, valueOf};
  tx.fields = () => [...document.querySelectorAll('[data-hk-field]')].map(el => {
    return {id: el.dataset.hkField, node: nodeOf(el), value: valueOf(el), control: kindOf(el),
            disabled: el.disabled, readOnly: el.readOnly};
  });
  tx.emit = (type, data = {}) => tx.trace.push({type, ...data, fields: tx.fields(),
                                                phase: tx.phase, ms: performance.now()});
  tx.beginEdit = (field, requested) => {
    if (editAction) throw new Error('An edit action is already pending');
    const targets = tx.fields().filter(item => item.id === field);
    if (targets.length !== 1 || targets[0].disabled || targets[0].readOnly)
      throw new Error('Unavailable or ambiguous edit target');
    delete tx.last[field];
    editAction = {id: ++actionSequence, field, requested, node: targets[0].node,
                  before: targets[0].value, sequence: eventSequence};
    tx.emit('edit-start', {field, requested, action: editAction.id, node: editAction.node});
    return editAction.id;
  };
  tx.completeEdit = action => {
    if (!editAction || editAction.id !== action) throw new Error('Unknown or completed edit action');
    const current = editAction;
    const evidence = tx.last[current.field];
    delete tx.last[current.field];
    editAction = null;
    const targets = tx.fields().filter(item => item.id === current.field);
    const target = targets[0];
    const available = targets.length === 1 && target.node === current.node &&
      !target.disabled && !target.readOnly;
    const fresh = available && evidence?.trusted === true && evidence.action === action &&
      evidence.sequence > current.sequence && evidence.node === target.node &&
      sameValue(evidence.value, current.requested) && sameValue(target.value, current.requested);
    // A confirmed already-satisfied action acknowledges no edit, not a new revision.
    // A fresh same-value native event still completes an edit and creates a revision.
    const noop = available && !evidence && sameValue(current.before, current.requested) &&
      sameValue(target.value, current.requested);
    const type = noop ? 'edit-noop' : 'edit';
    // A no-op must still expose any loss of an existing live obligation.
    if (noop) tx.emit('checkpoint');
    tx.emit(type, {field: current.field, requested: current.requested, action,
                   trusted: fresh, nativeSequence: evidence?.sequence ?? null});
    return type;
  };
  for (const kind of ['input', 'change']) document.addEventListener(kind, event => {
    const el = event.target;
    if (el.matches && el.matches('[data-hk-field]')) {
      const field = el.dataset.hkField;
      const evidence = {trusted: event.isTrusted, value: valueOf(el), event: kind,
                        node: nodeOf(el), sequence: ++eventSequence,
                        action: editAction?.field === field ? editAction.id : null};
      tx.last[field] = evidence;
      tx.emit('native-' + kind, {field, trusted: evidence.trusted, eventValue: evidence.value,
                                node: evidence.node, sequence: evidence.sequence, action: evidence.action});
    }
  }, true);
  tx.enqueue = (consumer, reader, onAck) => {
    const id = 't' + (++tx.count);
    tx.emit('consume', {consumer, transaction: id});
    tx.pending.set(id, {consumer, reader, onAck, sent: false});
    return id;
  };
  tx.settle = () => new Promise(resolve => setTimeout(resolve, 0));
  tx.release = async id => {
    const item = tx.pending.get(id);
    if (!item || item.sent) throw new Error('Unknown or duplicate dispatch');
    item.sent = true;
    const body = JSON.stringify(item.reader());
    tx.emit('dispatch', {transaction: id, consumer: item.consumer, body});
    const reply = await fetch(ENDPOINT + '/submit?run=' + encodeURIComponent(RUN + ':' + id), {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body, signal: AbortSignal.timeout(5000)
    });
    if (!reply.ok) throw new Error('HTTP receiver rejected transaction');
    if (item.onAck) item.onAck(id);
    await tx.settle();
    tx.emit('ack', {transaction: id, consumer: item.consumer});
    tx.emit('checkpoint');
    return item.consumer;
  };
})();
