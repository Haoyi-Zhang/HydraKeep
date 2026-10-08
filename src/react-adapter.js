(() => {
  const R = React, h = R.createElement;
  window.makeApp = (cfg, prerender=false) => {
    const adopted = !prerender && cfg.design === 'adopt' ? __hk.snapshot().fields[0].value : cfg.initial;
    function Form() {
      const [value,setValue] = R.useState(adopted), [tick,setTick] = R.useState(0), [revision,setRevision] = R.useState(0), [removed,setRemoved] = R.useState(false), [ready,setReady] = R.useState(false);
      const unmanaged = ['uncontrolled','shadow','native','replace-uncontrolled'].includes(cfg.design);
      const onChange = e => {__hk.emit('framework-event', {eventValue:__hk.read(e.target)}); setValue(__hk.read(e.target));};
      R.useLayoutEffect(() => {
        __hk.api = {read:()=>value,
          commit:()=>ReactDOMBase.flushSync(()=>{setTick(x=>x+1);if(cfg.design==='authority')setValue(cfg.initial);}),
          transition:()=>ReactDOMBase.flushSync(()=>{if(cfg.design.startsWith('replace'))setRevision(x=>x+1);else if(cfg.design==='remove')setRemoved(true);else setTick(x=>x+1);}),
          reset:()=>ReactDOMBase.flushSync(()=>setValue(cfg.initial))};
        if (!prerender && cfg.design==='disabled' && !ready) setReady(true);
      });
      let controlProps = {name:'value', 'data-hk-field':'toy-field', 'aria-label':'Toy field', key:revision, disabled:cfg.design==='disabled'&&!ready, onChange};
      if (cfg.kind==='checkbox') Object.assign(controlProps,{type:'checkbox',value:'on',[unmanaged?'defaultChecked':'checked']:unmanaged?cfg.initial:value});
      else Object.assign(controlProps,{[unmanaged?'defaultValue':'value']:unmanaged?cfg.initial:value});
      let control;
      if(cfg.kind==='select')control=h('select',controlProps,h('option',{value:'A'},'A'),h('option',{value:'B'},'B'),h('option',{value:'C'},'C'));
      else if(cfg.kind==='textarea')control=h('textarea',controlProps);
      else control=h('input',{...controlProps,type:cfg.kind==='checkbox'?'checkbox':'text'});
      const submit=e=>{if(['native','uncontrolled','replace-uncontrolled'].includes(cfg.design))return;e.preventDefault();void __hk.post(removed?null:value);};
      return h('form',{method:'POST',action:'/submit?run='+encodeURIComponent(window.RUN),target:'receipt',onSubmit:submit,'data-tick':tick},
        removed?null:control,h('button',{type:'submit',id:'submit'},'Submit'),h('button',{type:'button',id:'reset',onClick:e=>{setValue(cfg.initial);__hk.emit('user-reset',{trusted:e.isTrusted});}},'Reset'));
    }
    return h(Form);
  };
  window.adapter = {
    async mount(cfg, prerender=false){
      const app=makeApp(cfg,prerender);
      if(prerender)ReactDOMBase.flushSync(()=>ReactDOM.createRoot(document.getElementById('root')).render(app));
      else ReactDOMBase.flushSync(()=>ReactDOM.hydrateRoot(document.getElementById('root'),app,{onRecoverableError:e=>__hk.emit('recoverable-error',{message:e.message})}));
      await new Promise(r=>setTimeout(r,0));
      if(!__hk.api)throw new Error('React layout effect did not register commit controller');
    }, async commit(){__hk.api.commit();}, async transition(cfg){if(cfg.design==='reset')document.getElementById('reset').click();else __hk.api.transition();}
  };
})();
