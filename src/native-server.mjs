import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import * as React from 'react';
import * as ReactDOMServer from 'react-dom/server';
import {createRequire} from 'node:module';
import {reactComponent} from './native/react-form.mjs';
import {vueComponent} from './native/vue-form.mjs';
const require=createRequire(import.meta.url),base=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const cases=[...JSON.parse(fs.readFileSync(path.join(base,'fixtures/multi/cases.json'))),...JSON.parse(fs.readFileSync(path.join(base,'fixtures/native/historical-cases.json')))];
const handlersContext={window:{}};vm.runInNewContext(fs.readFileSync(path.join(base,'fixtures/multi/handlers.js'),'utf8'),handlersContext);const handlers=handlersContext.window.HANDLERS;
const records=new Map(),documents=new Map();
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const js=x=>JSON.stringify(x).replace(/</g,'\\u003c');
const server=http.createServer(async(req,res)=>{
 try{
  const u=new URL(req.url,'http://localhost');
  if(u.pathname==='/health')return res.end('ok');
  if(u.pathname==='/records'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(records.get(u.searchParams.get('run'))||[]));}
  if(u.pathname==='/document'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(documents.get(u.searchParams.get('run'))));}
  if(u.pathname==='/submit'&&req.method==='POST'){
   let body='';for await(const c of req){body+=c;if(body.length>16384)throw Error('oversized local body');}
   const run=u.searchParams.get('run');const row={run,body,contentType:req.headers['content-type'],receivedAt:Date.now()};records.set(run,[...(records.get(run)||[]),row]);res.setHeader('Content-Type','text/html');return res.end('<p>Local receipt</p>');
  }
  if(u.pathname==='/native'){
   const item=cases.find(x=>x.id===u.searchParams.get('id'));if(!item){res.writeHead(404);return res.end('unknown case');}
   const run=u.searchParams.get('run'),tag=u.searchParams.get('version')||'original';
   const cfg={...item,nativeSubmit:u.searchParams.get('native')==='1',nativeAction:'/submit?run='+encodeURIComponent(run)};
   const observer={fields:()=>[],read:()=>{throw Error('SSR read of DOM')},emit:()=>{},post:()=>{throw Error('SSR post')}};
   let markup,renderer,version;
   if(cfg.framework==='react'){
    const App=reactComponent(React,cfg,observer,handlers,{},false);markup=ReactDOMServer.renderToString(React.createElement(App));renderer='react-dom/server.renderToString';version=React.version;
   }else{
    const pkg=tag==='original'?'vue':'vue-'+tag,rendererPkg=tag==='original'?'@vue/server-renderer':'renderer-'+tag;
    const S=require(rendererPkg),rendererRequire=createRequire(require.resolve(rendererPkg));
    const V=tag==='original'?require(pkg):rendererRequire('@vue/runtime-dom');
    markup=await S.renderToString(V.createSSRApp(vueComponent(V,cfg,observer,handlers,false)));renderer=rendererPkg+'.renderToString';version=V.version;
   }
   documents.set(run,{run,case:cfg.id,markup,markup_sha256:hash(markup),renderer,version,node:process.version});
   res.setHeader('Content-Type','text/html; charset=utf-8');res.setHeader('Cache-Control','no-store');
   return res.end('<!doctype html><html><head><meta charset="utf-8"><title>HydraKeep native SSR case</title><style>body{padding:16px}input,textarea,select,button{font-size:18px;margin:5px}</style></head><body><div id="root">'+markup+'</div><iframe name="receipt" hidden></iframe><script>window.CFG='+js(cfg)+';window.RUN='+js(run)+';window.ENDPOINT=location.origin;</script><script src="/src/multi-observer.js"></script></body></html>');
  }
  const p=path.resolve(base,'.'+u.pathname);
  if(!p.startsWith(base+path.sep)||!fs.existsSync(p)||!fs.statSync(p).isFile()){res.writeHead(404);return res.end();}
  res.setHeader('Content-Type',/\.(js|mjs)$/.test(p)?'text/javascript':'text/plain');fs.createReadStream(p).pipe(res);
 }catch(e){res.writeHead(500);res.end(String(e));}
});
server.listen(Number(process.env.PORT||8770),'127.0.0.1',()=>console.log('Native SSR ready'));
