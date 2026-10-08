/* Read-only value observer. It never assigns form values or determines verdicts. */
(() => {
  const nodes = new WeakMap(); let nextNode = 1;
  const hk = window.__hk = {trace: [], phase: 'server-visible', appValue: null, api: null};
  hk.read = el => el.type === 'checkbox' ? el.checked : el.tagName === 'SELECT' && el.multiple ? Array.from(el.selectedOptions, x => x.value) : el.value;
  hk.snapshot = () => {
    const els = [...document.querySelectorAll('[data-hk-field="toy-field"]')];
    return {phase: hk.phase, fields: els.map(el => {
      if (!nodes.has(el)) nodes.set(el, nextNode++);
      return {id: 'toy-field', node: nodes.get(el), tag: el.tagName, value: hk.read(el), attribute: el.getAttribute('value'), checkedAttribute: el.hasAttribute('checked'), disabled: el.disabled, readOnly: !!el.readOnly};
    }), appValue: hk.api ? hk.api.read() : hk.appValue};
  };
  hk.emit = (type, detail = {}) => {const e = {seq: hk.trace.length, ms: performance.now(), type, ...detail, ...hk.snapshot()}; hk.trace.push(e); return e;};
  for (const event of ['input','change']) document.addEventListener(event, e => {
    if (e.target.matches('[data-hk-field]')) hk.emit('native-'+event, {trusted: e.isTrusted, eventValue: hk.read(e.target)});
  }, true);
  hk.post = async value => {
    if(window.OBSERVATION_ONLY){hk.emit('application-intent', {submittedValue:value});return;}
    const response = await fetch(window.ENDPOINT+'/submit?run='+encodeURIComponent(window.RUN), {method:'POST',headers:{'Content-Type':'application/json'}, body:JSON.stringify({value})});
    if (!response.ok) throw new Error('local endpoint rejected submission');
    hk.emit('application-submitted', {submittedValue:value,transport:'application-fetch'});
  };
  document.addEventListener('submit', e => {
    const f=new FormData(e.target); const el=e.target.querySelector('[data-hk-field]');
    hk.emit('native-serialization',{serializedValue:el?.type==='checkbox'?f.has('value'):(f.get('value') ?? null),defaultPrevented:e.defaultPrevented});
    if(!e.defaultPrevented){
      // A disclosed harness bridge, not a native browser navigation.
      e.preventDefault();
      const data=new URLSearchParams(f);
      fetch(window.ENDPOINT+'/submit?run='+encodeURIComponent(window.RUN),{method:'POST',body:data})
        .then(r=>{if(!r.ok)throw Error('local bridge rejected');hk.emit('native-bridge-submitted')})
        .catch(e=>hk.emit('transport-error',{message:String(e)}));
    }
  });
  hk.noise = () => {document.getElementById('unrelated').textContent += '.'; hk.emit('independent-region-update');};
})();
