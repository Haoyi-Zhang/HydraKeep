(()=>{
 const nodes=new WeakMap();let next=0;
 const hk=window.hk={trace:[],phase:'pre',api:null};
 hk.read=el=>el.type==='checkbox'?el.checked:el.value;
 hk.fields=()=>[...document.querySelectorAll('[data-hk-field]')].map(el=>{
  if(!nodes.has(el))nodes.set(el,++next);
  return {id:el.dataset.hkField,value:hk.read(el),node:nodes.get(el),disabled:el.disabled,readOnly:!!el.readOnly};
 });
 hk.emit=(type,detail={})=>{hk.trace.push({type,...detail,phase:hk.phase,fields:hk.fields(),ms:performance.now()});};
 hk.last={};
 for(const name of ['input','change'])document.addEventListener(name,e=>{
  if(e.target.matches('[data-hk-field]'))hk.last[e.target.dataset.hkField]={trusted:e.isTrusted,value:hk.read(e.target)};
 },true);
 hk.post=async(payload)=>{
  hk.emit('application-intent',{payload});
  const r=await fetch(ENDPOINT+'/submit?run='+encodeURIComponent(RUN),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(!r.ok)throw Error('local receiver rejected');hk.emit('ack');
 };
})();
