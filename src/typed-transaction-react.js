/* React implementation of heterogeneous, overlapping form consumers. */
(() => {
  const h = React.createElement;
  const fieldNames = ['name', 'agree', 'tier'];
  window.txApp = {async mount(cfg, prerender = false) {
    const initial = {name: 'seed-name', agree: false, tier: 'basic'};
    if (!prerender) for (const field of tx.fields()) initial[field.id] = field.value;
    const scoped = ['scoped-submit', 'overbroad-clear'].includes(cfg.pattern);
    function App() {
      const [state, setState] = React.useState(initial);
      const [tierRemoved, setTierRemoved] = React.useState(false);
      const [nameGeneration, setNameGeneration] = React.useState(0);
      const live = React.useRef(state); live.current = state;
      function submit(event) {
        event.preventDefault();
        const consumer = scoped ? (tx.count === 0 ? 'identity' : 'consent') : 'all';
        const names = consumer === 'identity' ? ['name', 'tier']
          : consumer === 'consent' ? ['agree'] : fieldNames;
        const pick = source => Object.fromEntries(names.map(name => [name, source[name]]));
        const frozen = pick(state);
        let reader = () => frozen;
        if (cfg.pattern === 'late-read') reader = () => pick(live.current);
        if (cfg.pattern === 'checkbox-coercion' && tx.count === 0)
          reader = () => ({...frozen, agree: String(frozen.agree)});
        if (cfg.pattern === 'stale-after-reset' && tx.count === 1)
          reader = () => ({...frozen, tier: 'basic'});
        tx.enqueue(consumer, reader, null);
        if (consumer === 'identity') {
          setTierRemoved(true);
          if (cfg.pattern === 'overbroad-clear') setState(old => ({...old, agree: false}));
        }
      }
      function resetTier(event) {
        tx.emit('transition', {name: 'reset-tier', trusted: event.isTrusted});
        setState(old => ({...old, tier: 'basic'}));
      }
      function replaceName() { setNameGeneration(generation => generation + 1); }
      const children = [
        h('label', {key: 'name-label'}, 'Name ', h('input', {
          key: 'name-' + nameGeneration, name: 'name', type: 'text', 'data-hk-field': 'name',
          value: state.name, onChange: event => setState(old => ({...old, name: event.target.value}))
        })),
        h('label', {key: 'agree-label'}, h('input', {
          key: 'agree', name: 'agree', type: 'checkbox', 'data-hk-field': 'agree',
          checked: state.agree, onChange: event => setState(old => ({...old, agree: event.target.checked}))
        }), ' Agree'),
      ];
      if (!tierRemoved) children.push(h('label', {key: 'tier-label'}, 'Tier ', h('select', {
        key: 'tier', name: 'tier', 'data-hk-field': 'tier', value: state.tier,
        onChange: event => setState(old => ({...old, tier: event.target.value}))
      }, [h('option', {key: 'basic', value: 'basic'}, 'Basic'),
          h('option', {key: 'pro', value: 'pro'}, 'Pro'),
          h('option', {key: 'enterprise', value: 'enterprise'}, 'Enterprise')])));
      children.push(h('button', {key: 'submit', id: 'submit', type: 'submit'}, 'Save'));
      children.push(h('button', {key: 'reset', id: 'reset-tier', type: 'button', onClick: resetTier}, 'Reset tier'));
      children.push(h('button', {key: 'replace', id: 'replace-name', type: 'button', onClick: replaceName}, 'Replace name'));
      return h('form', {onSubmit: submit}, children);
    }
    if (prerender) ReactDOMBase.flushSync(() => ReactDOM.createRoot(document.getElementById('root')).render(h(App)));
    else ReactDOMBase.flushSync(() => ReactDOM.hydrateRoot(document.getElementById('root'), h(App)));
    await tx.settle();
  }};
})();
