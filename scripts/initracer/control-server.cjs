const http=require('http'),fs=require('fs');
const instrumentHTML=require('./src/instrumentation/instrument-html.js');
const instrumentJS=require('./src/instrumentation/instrument-js.js');
const records=new Map();
const cases=['overwrite','shadow','adopt','reset'];
http.createServer(async(req,res)=>{
 const u=new URL(req.url,'http://localhost');const id=u.searchParams.get('case'),run=u.searchParams.get('run'),mode=u.searchParams.get('mode');
 if(u.pathname==='/health')return res.end('ok');
 if(u.pathname==='/records'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(records.get(run)||[]));}
 if(u.pathname==='/submit'){let s='';for await(const c of req)s+=c;records.set(run,[...(records.get(run)||[]),{body:s,contentType:req.headers['content-type']}]);return res.end('ok');}
 if(u.pathname==='/boot.js'){
  let js="var state='seed';var input=document.getElementById('a');";
  if(id==='overwrite')js+="input.value='seed';";
  if(id==='adopt'||id==='reset')js+="state=input.value;";
  js+="document.getElementById('submit').onclick=function(){fetch('/submit?run='+encodeURIComponent("+JSON.stringify(run)+"),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({a:state})});};document.getElementById('reset').onclick=function(){state='seed';input.value='seed';};window.ready=true;";
  if(mode!=='none')js=instrumentJS(js,{allowReturnOutsideFunction:false,isExternal:true,url:'http://127.0.0.1:8776/boot.js?sync=0'});
  res.setHeader('Content-Type','text/javascript; charset=utf-8');return res.end(js);
 }
 if(u.pathname==='/'){
  let html='<!doctype html><html><head><title>Local semantic control</title></head><body><input id="a" name="a" data-hk-field="a" value="seed"><button id="submit">Submit</button><button id="reset">Reset</button><script async src="/boot.js?case='+id+'&run='+run+'&mode='+mode+'"></script></body></html>';
  if(mode!=='none'){process.env.INITRACER_MODE=mode;process.env.INITRACER_URL='http://127.0.0.1:8776/';html=instrumentHTML(html);}
  res.setHeader('Content-Type','text/html; charset=utf-8');return res.end(html);
 }
 res.writeHead(404);res.end();
}).listen(8776,'127.0.0.1');
