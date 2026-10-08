/* Observation and loopback transport for heterogeneous form controls.
   The adapter records typed live values; it never decides contract correctness. */
(() => {
  const ids = new WeakMap(); let serial = 0;
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
    if (!ids.has(el)) ids.set(el, ++serial);
    return {id: el.dataset.hkField, node: ids.get(el), value: valueOf(el), control: kindOf(el),
            disabled: el.disabled, readOnly: el.readOnly};
  });
  tx.emit = (type, data = {}) => tx.trace.push({type, ...data, fields: tx.fields(),
                                                phase: tx.phase, ms: performance.now()});
  for (const kind of ['input', 'change']) document.addEventListener(kind, event => {
    const el = event.target;
    if (el.matches && el.matches('[data-hk-field]'))
      tx.last[el.dataset.hkField] = {trusted: event.isTrusted, value: valueOf(el), event: kind};
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
