/* Authored controlled workflows, with explicit ordinary framework handlers. */
(() => {
  const h = React.createElement;
  window.txApp = {async mount(cfg, prerender = false) {
    let initial = {a: 'seed-a', b: 'seed-b'};
    if (!prerender) for (const f of tx.fields()) initial[f.id] = f.value;
    const scoped = ['scoped-submit', 'overbroad-clear'].includes(cfg.pattern);
    function App() {
      const [state, setState] = React.useState(initial);
      const [removed, setRemoved] = React.useState(false);
      const live = React.useRef(state); live.current = state;
      const mounted = React.useRef({...initial});
      function submit(event) {
        event.preventDefault();
        const consumer = scoped ? (tx.count === 0 ? 'onlyA' : 'onlyB') : 'all';
        const names = consumer === 'onlyA' ? ['a'] : consumer === 'onlyB' ? ['b'] : ['a','b'];
        const pick = s => Object.fromEntries(names.map(f => [f,s[f]]));
        const frozen = pick(state);
        let reader = () => frozen;
        if (cfg.pattern === 'late-read') reader = () => pick(live.current);
        if (cfg.pattern === 'stale-closure') reader = () => pick(mounted.current);
        if (cfg.pattern === 'stale-after-reset' && tx.count === 1)
          reader = () => ({...frozen, a: 'seed-a'});
        const ack = cfg.pattern === 'ack-clear' ? id => {
          if (id === 't1') ReactDOMBase.flushSync(() => setState(s => ({...s,a:'seed-a'})));
        } : null;
        tx.enqueue(consumer, reader, ack);
        if (consumer === 'onlyA') {
          setRemoved(true);
          if (cfg.pattern === 'overbroad-clear') setState(s => ({...s,b:'seed-b'}));
        }
      }
      function reset(event) {
        tx.emit('transition', {name: 'reset-a', trusted: event.isTrusted});
        setState(s => ({...s,a:'seed-a'}));
      }
      return h('form', {onSubmit: submit},
        ...['a','b'].filter(f => !(removed && f === 'a')).map(f => h('input', {
          key:f, name:f, type:'text', 'data-hk-field':f, value:state[f],
          onChange:e => setState(s => ({...s,[f]:e.target.value}))})),
        h('button',{id:'submit',type:'submit'},'Save'),
        h('button',{id:'reset-a',type:'button',onClick:reset},'Reset A'));
    }
    if (prerender) ReactDOMBase.flushSync(() => ReactDOM.createRoot(document.getElementById('root')).render(h(App)));
    else ReactDOMBase.flushSync(() => ReactDOM.hydrateRoot(document.getElementById('root'),h(App)));
    await tx.settle();
  }};
})();
