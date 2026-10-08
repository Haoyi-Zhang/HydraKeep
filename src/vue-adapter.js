(() => {
  const V=Vue, h=V.h;
  window.adapter={
    async mount(cfg,prerender=false){
      const adopted=!prerender&&cfg.design==='adopt'?__hk.snapshot().fields[0].value:cfg.initial;
      const component={setup(){
        const value=V.ref(adopted), tick=V.ref(0),revision=V.ref(0),removed=V.ref(false),ready=V.ref(false);
        const unmanaged=['uncontrolled','shadow','native','replace-uncontrolled'].includes(cfg.design);
        const update=x=>{value.value=x;__hk.emit('framework-event',{eventValue:x});};
        V.onMounted(()=>{if(!prerender&&cfg.design==='disabled')ready.value=true;});
        __hk.api={read:()=>value.value,
          commit:()=>{tick.value++;if(cfg.design==='authority')value.value=cfg.initial;},
          transition:()=>{if(cfg.design.startsWith('replace'))revision.value++;else if(cfg.design==='remove')removed.value=true;else tick.value++;},
          reset:()=>{value.value=cfg.initial;}};
        return ()=>{
          let props={name:'value','data-hk-field':'toy-field','aria-label':'Toy field',key:revision.value,disabled:cfg.design==='disabled'&&!ready.value};
          const tag=cfg.kind==='textarea'?'textarea':cfg.kind==='select'?'select':'input';
          if(tag==='input')props.type=cfg.kind==='checkbox'?'checkbox':'text';
          if(unmanaged){props[cfg.kind==='checkbox'?'checked':'value']=cfg.initial;props.onInput=e=>update(__hk.read(e.target));props.onChange=e=>update(__hk.read(e.target));}
          else props['onUpdate:modelValue']=update;
          if(cfg.kind==='checkbox')props.value='on';
          let field=h(tag,props,cfg.kind==='select'?[h('option',{value:'A'},'A'),h('option',{value:'B'},'B'),h('option',{value:'C'},'C')]:null);
          if(!unmanaged)field=V.withDirectives(field,[[cfg.kind==='checkbox'?V.vModelCheckbox:cfg.kind==='select'?V.vModelSelect:V.vModelText,value.value]]);
          return h('form',{method:'POST',action:'/submit?run='+encodeURIComponent(window.RUN),target:'receipt','data-tick':tick.value,onSubmit:e=>{
            if(['native','uncontrolled','replace-uncontrolled'].includes(cfg.design))return;e.preventDefault();void __hk.post(removed.value?null:value.value);
          }},[removed.value?null:field,h('button',{type:'submit',id:'submit'},'Submit'),h('button',{type:'button',id:'reset',onClick:e=>{__hk.api.reset();__hk.emit('user-reset',{trusted:e.isTrusted});}},'Reset')]);
        };
      }};
      const app=(prerender?V.createApp:V.createSSRApp)(component);app.mount('#root');await V.nextTick();
    },async commit(){__hk.api.commit();await V.nextTick();},async transition(){__hk.api.transition();await V.nextTick();},async settle(){await V.nextTick();}
  };
})();
