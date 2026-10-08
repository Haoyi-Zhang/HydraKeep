/* Vue implementation paired with the heterogeneous React workflows. */
(() => {
  const {h, reactive, ref, createSSRApp, createApp, nextTick} = Vue;
  const fieldNames = ['name', 'agree', 'tier'];
  window.txApp = {async mount(cfg, prerender = false) {
    const initial = {name: 'seed-name', agree: false, tier: 'basic'};
    if (!prerender) for (const field of tx.fields()) initial[field.id] = field.value;
    const scoped = ['scoped-submit', 'overbroad-clear'].includes(cfg.pattern);
    const App = {setup() {
      const state = reactive({...initial});
      const tierRemoved = ref(false), nameGeneration = ref(0);
      function submit(event) {
        event.preventDefault();
        const consumer = scoped ? (tx.count === 0 ? 'identity' : 'consent') : 'all';
        const names = consumer === 'identity' ? ['name', 'tier']
          : consumer === 'consent' ? ['agree'] : fieldNames;
        const pick = source => Object.fromEntries(names.map(name => [name, source[name]]));
        const frozen = pick(state);
        let reader = () => frozen;
        if (cfg.pattern === 'late-read') reader = () => pick(state);
        if (cfg.pattern === 'checkbox-coercion' && tx.count === 0)
          reader = () => ({...frozen, agree: String(frozen.agree)});
        if (cfg.pattern === 'stale-after-reset' && tx.count === 1)
          reader = () => ({...frozen, tier: 'basic'});
        tx.enqueue(consumer, reader, null);
        if (consumer === 'identity') {
          tierRemoved.value = true;
          if (cfg.pattern === 'overbroad-clear') state.agree = false;
        }
      }
      function resetTier(event) {
        tx.emit('transition', {name: 'reset-tier', trusted: event.isTrusted});
        state.tier = 'basic';
      }
      return () => h('form', {onSubmit: submit}, [
        h('label', {key: 'name-label'}, ['Name ', h('input', {
          key: 'name-' + nameGeneration.value, name: 'name', type: 'text', 'data-hk-field': 'name',
          value: state.name, onInput: event => state.name = event.target.value
        })]),
        h('label', {key: 'agree-label'}, [h('input', {
          key: 'agree', name: 'agree', type: 'checkbox', 'data-hk-field': 'agree',
          checked: state.agree, onChange: event => state.agree = event.target.checked
        }), ' Agree']),
        !tierRemoved.value && h('label', {key: 'tier-label'}, ['Tier ', h('select', {
          key: 'tier', name: 'tier', 'data-hk-field': 'tier', value: state.tier,
          onChange: event => state.tier = event.target.value
        }, [h('option', {value: 'basic'}, 'Basic'), h('option', {value: 'pro'}, 'Pro'),
            h('option', {value: 'enterprise'}, 'Enterprise')])]),
        h('button', {id: 'submit', type: 'submit'}, 'Save'),
        h('button', {id: 'reset-tier', type: 'button', onClick: resetTier}, 'Reset tier'),
        h('button', {id: 'replace-name', type: 'button', onClick: () => nameGeneration.value++}, 'Replace name')
      ]);
    }};
    (prerender ? createApp(App) : createSSRApp(App)).mount('#root');
    await nextTick(); await tx.settle();
  }};
})();
