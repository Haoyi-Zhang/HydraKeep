(()=>{
 const h=React.createElement;
 window.multi={async mount(cfg,prerender=false){
  const init=Object.fromEntries(cfg.fields.map(f=>[f.id,f.initial]));
  if(!prerender&&cfg.adopt)for(const f of hk.fields())init[f.id]=f.value;
  function App(){
   const [s,setS]=React.useState(init),[tick,setTick]=React.useState(0),[rev,setRev]=React.useState(0),[removed,setRemoved]=React.useState(false),[ready,setReady]=React.useState(false);
   function change(fid,v){setS(old=>{let n={...old};HANDLERS[cfg.handlers[fid]](n,v);return n;});}
   function transition(trusted){
    if(cfg.pattern==='local-reset'||cfg.pattern==='shared-reset'){
     hk.emit('transition',{name:'reset',trusted});setS(old=>({...old,a:cfg.fields[0].initial,...(cfg.pattern==='shared-reset'?{b:cfg.fields[1].initial}:{})}));
    }else if(cfg.pattern==='remove'){hk.emit('transition',{name:'remove',trusted});setRemoved(true);}
    else if(cfg.pattern==='keyed')setRev(x=>x+1);else setTick(x=>x+1);
   }
   React.useLayoutEffect(()=>{hk.api={commit:()=>ReactDOMBase.flushSync(()=>setTick(x=>x+1)),transition:()=>ReactDOMBase.flushSync(()=>transition(false))};if(!prerender&&cfg.pattern==='disabled'&&!ready)setReady(true);});
   const fields=cfg.fields.filter(f=>!(removed&&f.id==='a')).map(f=>{
    let unmanaged=cfg.bindings[f.id]==='uncontrolled';let p={key:f.id+':'+rev,name:f.id,'data-hk-field':f.id,disabled:cfg.pattern==='disabled'&&!ready,onChange:e=>change(f.id,hk.read(e.target))};
    if(f.kind==='checkbox')Object.assign(p,{type:'checkbox',value:'on',[unmanaged?'defaultChecked':'checked']:unmanaged?f.initial:s[f.id]});else p[unmanaged?'defaultValue':'value']=unmanaged?f.initial:s[f.id];
    if(f.kind==='select')return h('select',p,h('option',{value:'A'},'A'),h('option',{value:'B'},'B'));
    if(f.kind==='textarea')return h('textarea',p);
    return h('input',{...p,type:f.kind==='checkbox'?'checkbox':'text'});
   });
   return h('form',{'data-tick':tick,onSubmit:e=>{e.preventDefault();let payload={...s};if(removed)delete payload.a;void hk.post(payload);}},...fields,h('button',{id:'submit',type:'submit'},'Submit'),h('button',{id:'transition',type:'button',onClick:e=>transition(e.isTrusted)},'Transition'));
  }
  if(prerender)ReactDOMBase.flushSync(()=>ReactDOM.createRoot(document.getElementById('root')).render(h(App)));
  else ReactDOMBase.flushSync(()=>ReactDOM.hydrateRoot(document.getElementById('root'),h(App)));
  await new Promise(r=>setTimeout(r,0));
 },async commit(){hk.api.commit();},async settle(){await new Promise(r=>setTimeout(r,0));}};
})();
