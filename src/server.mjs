import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const records=new Map();
export function createServer(fixtures){
  return http.createServer(async(req,res)=>{
    try{
      const u=new URL(req.url,'http://localhost');
      // Local toy endpoint: allow the opaque origin of offline experiment pages.
      res.setHeader('Access-Control-Allow-Origin','*');
      if(req.method==='OPTIONS'){
        res.setHeader('Access-Control-Allow-Headers','Content-Type');
        res.setHeader('Access-Control-Allow-Methods','POST,GET,OPTIONS');
        res.setHeader('Access-Control-Allow-Private-Network','true');
        res.writeHead(204);res.end();return;
      }
      if(u.pathname==='/submit'&&req.method==='POST'){
        let body='';for await(const c of req){body+=c;if(body.length>8192)throw new Error('body too large');}
        const run=u.searchParams.get('run'); const row={contentType:req.headers['content-type'],body,receivedAt:Date.now()};
        records.set(run,[...(records.get(run)||[]),row]);res.writeHead(200,{'Content-Type':'text/html'});res.end('<p>Recorded local toy value</p>');return;
      }
      if(u.pathname==='/records'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(records.get(u.searchParams.get('run'))||[]));return;}
      if(u.pathname==='/case'||u.pathname==='/render'){
        const cfg=fixtures.find(x=>x.id===u.searchParams.get('id'));if(!cfg){res.writeHead(404).end();return;}
        let markup='';
        const renderedFile=path.join(base,'fixtures','rendered.json');
        if(u.pathname==='/case'&&fs.existsSync(renderedFile))markup=JSON.parse(fs.readFileSync(renderedFile,'utf8'))[cfg.id]?.html||'';
        const run=u.searchParams.get('run')||'prerender';
        res.writeHead(200,{'Content-Type':'text/html','Cache-Control':'no-store'});
        res.end(`<!doctype html><html><head><meta charset="utf-8"><title>Local toy form</title><style>body{font:18px sans-serif;padding:30px}input,textarea,select,button{font:inherit;margin:10px;padding:8px}iframe{display:none}</style></head><body><p id="unrelated">Independent region</p><div id="root">${markup}</div><iframe name="receipt"></iframe><script>window.CFG=${JSON.stringify(cfg)};window.RUN=${JSON.stringify(run)};</script><script src="/src/observer.js"></script></body></html>`);return;
      }
      if(u.pathname==='/health'){res.end('ok');return;}
      const p=path.resolve(base,'.'+u.pathname);
      if(!p.startsWith(base+path.sep)||!fs.existsSync(p)||!fs.statSync(p).isFile()){res.writeHead(404).end();return;}
      res.writeHead(200,{'Content-Type':p.endsWith('.js')||p.endsWith('.mjs')?'text/javascript':p.endsWith('.json')?'application/json':'text/plain'});fs.createReadStream(p).pipe(res);
    }catch(e){res.writeHead(500);res.end(String(e));}
  });
}
const fixtures=JSON.parse(fs.readFileSync(path.join(base,'fixtures','cases.json'),'utf8'));
const server=createServer(fixtures);server.listen(Number(process.env.PORT||8765),'127.0.0.1',()=>console.log('HydraKeep localhost server ready'));
