export function vueComponent(V,cfg,hk,HANDLERS,client=false){
 const h=V.h;
 const init=Object.fromEntries(cfg.fields.map(f=>[f.id,f.initial]));
 if(client&&cfg.adopt)for(const f of hk.fields())init[f.id]=f.value;
  const component={setup(){
   const s=V.reactive(init),tick=V.ref(0),rev=V.ref(0),removed=V.ref(false),ready=V.ref(false);
   const change=(fid,v)=>HANDLERS[cfg.handlers[fid]](s,v);
   function transition(trusted){
    if(cfg.pattern==='local-reset'||cfg.pattern==='shared-reset'){
     hk.emit('transition',{name:'reset',trusted});s.a=cfg.fields[0].initial;if(cfg.pattern==='shared-reset')s.b=cfg.fields[1].initial;
    }else if(cfg.pattern==='remove'){hk.emit('transition',{name:'remove',trusted});removed.value=true;}
    else if(cfg.pattern==='keyed')rev.value++;else tick.value++;
   }
   hk.api={commit:()=>tick.value++,transition:()=>transition(false)};
   V.onMounted(()=>{if(client&&cfg.pattern==='disabled')ready.value=true;});
   return ()=>{
    const fields=cfg.fields.filter(f=>!(removed.value&&f.id==='a')).map(f=>{
     const p={key:f.id+':'+rev.value,name:f.id,'data-hk-field':f.id,disabled:cfg.pattern==='disabled'&&!ready.value};
     const tag=f.kind==='textarea'?'textarea':f.kind==='select'?'select':'input';
     if(tag==='input')p.type=f.kind;
     if(cfg.bindings[f.id]==='uncontrolled'){p[f.kind==='checkbox'?'checked':'value']=f.initial;p.onInput=e=>change(f.id,hk.read(e.target));p.onChange=e=>change(f.id,hk.read(e.target));}
     else p['onUpdate:modelValue']=v=>change(f.id,v);
     if(f.kind==='checkbox')p.value='on';
     let field=h(tag,p,tag==='select'?[h('option',{value:'A'},'A'),h('option',{value:'B'},'B')]:null);
     if(cfg.bindings[f.id]!=='uncontrolled')field=V.withDirectives(field,[[f.kind==='checkbox'?V.vModelCheckbox:f.kind==='select'?V.vModelSelect:V.vModelText,s[f.id]]]);return field;
    });
    return h('form',{'data-tick':tick.value,action:cfg.nativeAction,target:'receipt',method:'post',onSubmit:cfg.nativeSubmit?undefined:e=>{e.preventDefault();let payload={...s};if(removed.value)delete payload.a;void hk.post(payload);}},[...fields,h('button',{id:'submit',type:'submit'},'Submit'),h('button',{id:'transition',type:'button',onClick:e=>transition(e.isTrusted)},'Transition')]);
   };
  }};
 return component;
}
