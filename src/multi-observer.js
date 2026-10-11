(()=>{
 const nodes=new WeakMap();let next=0,sequence=0,actions=0,editing=null;
 const nodeOf=el=>{if(!nodes.has(el))nodes.set(el,++next);return nodes.get(el);};
 const hk=window.hk={trace:[],phase:'pre',api:null};
 hk.read=el=>el.type==='checkbox'?el.checked:el.value;
 hk.fields=()=>[...document.querySelectorAll('[data-hk-field]')].map(el=>{
  return {id:el.dataset.hkField,value:hk.read(el),node:nodeOf(el),disabled:el.disabled,readOnly:!!el.readOnly};
 });
 hk.emit=(type,detail={})=>{hk.trace.push({type,...detail,phase:hk.phase,fields:hk.fields(),ms:performance.now()});};
 hk.last={};
 hk.beginEdit=(field,requested)=>{
  const targets=hk.fields().filter(f=>f.id===field);
  if(editing||targets.length!==1||targets[0].disabled||targets[0].readOnly)throw Error('Unavailable or pending action');
  delete hk.last[field];editing={field,requested,node:targets[0].node,action:++actions,before:targets[0].value};
  hk.emit('edit-start',{field,requested,node:editing.node,action:editing.action});return editing.action;
 };
 hk.completeEdit=action=>{
  if(!editing||editing.action!==action)throw Error('Unknown or completed action');
  const current=editing,evidence=hk.last[current.field],targets=hk.fields().filter(f=>f.id===current.field);
  delete hk.last[current.field];editing=null;
  const target=targets[0],available=targets.length===1&&target.node===current.node&&!target.disabled&&!target.readOnly;
  const fresh=available&&evidence?.trusted===true&&evidence.action===action&&evidence.node===current.node&&
   Object.is(evidence.value,current.requested)&&Object.is(target.value,current.requested);
  const noop=available&&!evidence&&Object.is(current.before,current.requested)&&Object.is(target.value,current.requested);
  if(noop)hk.emit('checkpoint');
  hk.emit(noop?'edit-noop':'edit',{field:current.field,requested:current.requested,action,trusted:fresh,nativeSequence:evidence?.sequence??null});
 };
 for(const name of ['input','change'])document.addEventListener(name,e=>{
  if(e.target.matches('[data-hk-field]')){
   const field=e.target.dataset.hkField,evidence={trusted:e.isTrusted,value:hk.read(e.target),node:nodeOf(e.target),
    sequence:++sequence,action:editing?.field===field?editing.action:null};hk.last[field]=evidence;
   hk.emit('native-'+name,{field,trusted:evidence.trusted,eventValue:evidence.value,node:evidence.node,sequence:evidence.sequence,action:evidence.action});
  }
 },true);
 document.addEventListener('submit',e=>hk.emit('consume',{trusted:e.isTrusted}),true);
 hk.post=async(payload)=>{
  hk.emit('application-intent',{payload});
  const r=await fetch(ENDPOINT+'/submit?run='+encodeURIComponent(RUN),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(!r.ok)throw Error('local receiver rejected');hk.emit('ack');
 };
})();
