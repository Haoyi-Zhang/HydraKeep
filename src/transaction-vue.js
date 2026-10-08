/* Paired Vue integration: normal reactive bindings, not a simulated DOM. */
(() => {
  const {h, reactive, ref, createSSRApp, createApp, nextTick} = Vue;
  window.txApp = {async mount(cfg, prerender = false) {
    const initial = {a:'seed-a',b:'seed-b'};
    if (!prerender) for (const f of tx.fields()) initial[f.id] = f.value;
    const scoped = ['scoped-submit','overbroad-clear'].includes(cfg.pattern);
    const App = {setup() {
      const state = reactive({...initial}), removed = ref(false), mounted = {...initial};
      function submit(event) {
        event.preventDefault();
        const consumer = scoped ? (tx.count === 0 ? 'onlyA' : 'onlyB') : 'all';
        const names = consumer === 'onlyA' ? ['a'] : consumer === 'onlyB' ? ['b'] : ['a','b'];
        const pick = s => Object.fromEntries(names.map(f => [f,s[f]]));
        const frozen = pick(state);
        let reader = () => frozen;
        if (cfg.pattern === 'late-read') reader = () => pick(state);
        if (cfg.pattern === 'stale-closure') reader = () => pick(mounted);
        if (cfg.pattern === 'stale-after-reset' && tx.count === 1)
          reader = () => ({...frozen,a:'seed-a'});
        const ack = cfg.pattern === 'ack-clear' ? id => {if (id === 't1') state.a = 'seed-a';} : null;
        tx.enqueue(consumer,reader,ack);
        if (consumer === 'onlyA') {
          removed.value = true;
          if (cfg.pattern === 'overbroad-clear') state.b='seed-b';
        }
      }
      function reset(event) {
        tx.emit('transition',{name:'reset-a',trusted:event.isTrusted});state.a='seed-a';
      }
      return () => h('form',{onSubmit:submit},[
        ...['a','b'].filter(f => !(removed.value && f === 'a')).map(f => h('input',{
          key:f,name:f,type:'text','data-hk-field':f,value:state[f],onInput:e => state[f]=e.target.value})),
        h('button',{id:'submit',type:'submit'},'Save'),
        h('button',{id:'reset-a',type:'button',onClick:reset},'Reset A')]);
    }};
    (prerender ? createApp(App) : createSSRApp(App)).mount('#root');
    await nextTick(); await tx.settle();
  }};
})();
