// Owned finite event-listener model. These objects are not browser evidence.
import fs from 'node:fs';
import vm from 'node:vm';

export function run(scenario) {
  class Input {
    constructor(field, value) {
      this.dataset = {hkField: field};
      this.type = field === 'agree' ? 'checkbox' : 'text';
      this.value = value; this.checked = value;
      this.disabled = false; this.readOnly = false;
    }
    matches(selector) { return selector === '[data-hk-field]'; }
  }
  const controls = [new Input('name', 'seed'), new Input('agree', false)];
  const listeners = {};
  const context = {window: {}, HTMLInputElement: Input, HTMLSelectElement: class {},
    HTMLTextAreaElement: class {}, performance: {now: () => 0},
    document: {querySelectorAll: () => controls,
               addEventListener: (kind, listener) => { listeners[kind] = listener; }}};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(new URL('../src/typed-transaction-observer.js', import.meta.url),
                                 'utf8'), context);
  const tx = context.window.tx;
  const control = field => controls.find(el => el.dataset.hkField === field);
  const set = (el, value) => { el.value = value; el.checked = value; };
  const native = (field, value, trusted = true, el = control(field)) => {
    set(el, value);
    listeners.input({target: el, isTrusted: trusted});
  };
  const edit = value => {
    const action = tx.beginEdit('agree', value);
    native('agree', value);
    tx.completeEdit(action);
    return action;
  };
  const consume = () => tx.enqueue('save', () => ({}));
  const receipt = (transaction, value) => tx.emit('receipt', {
    transaction, consumer: 'save', channel: 'application', payload: {agree: value}});
  const reset = () => {
    tx.emit('transition', {name: 'reset', trusted: true});
    set(control('agree'), false); tx.emit('checkpoint');
  };
  let error = null;
  if (scenario === 'duplicate-check') {
    edit(true); const first = consume(); receipt(first, true);
    // A check of an already checked box supplies no input/change event.
    tx.completeEdit(tx.beginEdit('agree', true));
  } else if (scenario === 'fresh-same-value') {
    edit(true); const first = consume(); edit(true); const second = consume();
    receipt(second, true); receipt(first, true);
  } else if (scenario === 'no-new-event-changed') {
    edit(true); const first = consume();
    const action = tx.beginEdit('agree', false); set(control('agree'), false);
    tx.completeEdit(action); receipt(first, true);
  } else if (scenario === 'untrusted') {
    set(control('agree'), true);
    const action = tx.beginEdit('agree', true); native('agree', true, false);
    tx.completeEdit(action); receipt(consume(), true);
  } else if (scenario === 'wrong-type' || scenario === 'wrong-value') {
    const action = tx.beginEdit('agree', scenario === 'wrong-type' ? 1 : true);
    native('agree', scenario === 'wrong-type' ? true : false);
    tx.completeEdit(action); receipt(consume(), control('agree').checked);
  } else if (scenario === 'replaced-node' || scenario === 'detached-event') {
    if (scenario === 'replaced-node') edit(true);
    const action = tx.beginEdit('agree', true), old = control('agree');
    controls[1] = new Input('agree', true);
    if (scenario === 'detached-event') native('agree', true, true, old);
    tx.completeEdit(action); receipt(consume(), true);
  } else if (scenario === 'wrong-field') {
    const action = tx.beginEdit('agree', true);
    native('name', 'toy'); set(control('agree'), true);
    tx.completeEdit(action); receipt(consume(), true);
  } else if (scenario === 'consumed-token') {
    const action = edit(true);
    try { tx.completeEdit(action); } catch (e) { error = e.message; }
    receipt(consume(), true);
  } else if (scenario === 'stale-before-start') {
    native('agree', true);
    const action = tx.beginEdit('agree', false); set(control('agree'), false);
    tx.completeEdit(action); receipt(consume(), false);
  } else if (scenario === 'reset-and-noop') {
    edit(true); const first = consume(); reset();
    tx.completeEdit(tx.beginEdit('agree', false)); const second = consume();
    receipt(second, false); receipt(first, true);
  } else if (scenario === 'reset-and-fresh') {
    edit(true); const first = consume(); reset(); edit(true); const second = consume();
    receipt(second, false); receipt(first, true);
  } else if (scenario === 'noop-after-loss') {
    edit(true); set(control('agree'), false);
    tx.completeEdit(tx.beginEdit('agree', false)); reset(); receipt(consume(), false);
  } else if (scenario === 'trace-cleared') {
    native('agree', true); tx.trace = [];
    edit(true); receipt(consume(), true);
  } else {
    throw new Error('Unknown owned scenario: ' + scenario);
  }
  return {trace: tx.trace, error, retainedEvidence: Object.keys(tx.last)};
}
