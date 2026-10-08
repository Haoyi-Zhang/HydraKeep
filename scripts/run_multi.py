#!/usr/bin/env python3
"""Actual two-field browser runs; application payload checked at local receiver."""
from __future__ import annotations
import pathlib,sys,json,subprocess,time,urllib.request,os,collections,argparse
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form,signature
from multi_explorer import pair_grid,pair_quotient,independent
CASES=json.loads((ROOT/'fixtures/multi/cases.json').read_text());CONTRACTS=json.loads((ROOT/'fixtures/multi/contracts.json').read_text());EFFECTS=json.loads((ROOT/'results/phase-grid/effects.json').read_text())['effects']
ENDPOINT='http://127.0.0.1:8766';counter=0

def init(p,cfg,markup=''):
 global counter
 counter+=1;p.set_default_timeout(4000)
 p.set_content('<html><head><style>body{padding:16px}input,textarea,select,button{font-size:18px;margin:5px}</style></head><body><div id="root">'+markup+'</div></body></html>')
 p.evaluate('(x)=>{window.CFG=x.cfg;window.RUN=x.run;window.ENDPOINT=x.endpoint}',dict(cfg=cfg,run=f'multi-{counter}',endpoint=ENDPOINT))
 p.add_script_tag(content=(ROOT/'src/multi-observer.js').read_text())
def load(p,cfg):
 v='19.1.1' if cfg['framework']=='react' else '3.5.13';p.add_script_tag(content=(ROOT/f'vendor/{cfg["framework"]}-{v}.production.js').read_text());p.add_script_tag(content=(ROOT/'fixtures/multi/handlers.js').read_text());p.add_script_tag(content=(ROOT/f'src/multi-{cfg["framework"]}.js').read_text())
def prerender(b,cfg):
 p=b.new_page();init(p,cfg);load(p,cfg);p.evaluate('multi.mount(CFG,true)')
 p.evaluate('''()=>{for(const e of document.querySelectorAll('[data-hk-field]')){
 if(e.type==='checkbox')e.toggleAttribute('checked',e.checked);else if(e.tagName==='SELECT'){for(const o of e.options)o.toggleAttribute('selected',o.selected);}else if(e.tagName==='TEXTAREA')e.textContent=e.value;else e.setAttribute('value',e.value);}}''')
 html=p.locator('#root').inner_html();p.close();return html

def edit(p,f):
 loc=p.locator('[data-hk-field="'+f['id']+'"]')
 if loc.count()==0:p.evaluate('(field)=>hk.emit("edit-absent",{field})',f['id']);return
 if loc.count()!=1:raise RuntimeError('ambiguous browser edit target')
 if not loc.is_enabled():p.evaluate('(field)=>hk.emit("edit-blocked",{field})',f['id']);return
 if f['kind']=='checkbox':loc.click()
 elif f['kind']=='select':loc.focus();loc.press('Home');loc.press('ArrowDown');loc.press('Enter')
 else:loc.click();loc.press('ControlOrMeta+A');loc.press_sequentially(f['edit'])
 p.evaluate('(f)=>hk.emit("edit",{field:f.id,requested:f.edit,trusted:hk.last[f.id]?.trusted===true})',f)

def execute(b,cfg,s,html,rep=0):
 start=time.perf_counter();p=b.new_page();errors=[];console=[];p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda m:console.append(m.text) if m.type in ['error','warning'] else None)
 row=dict(case=cfg['id'],framework=cfg['framework'],pattern=cfg['pattern'],split=cfg['split'],schedule=s.as_dict(),rep=rep,evidence_class='offline-real-chromium-loopback-fetch')
 try:
  init(p,cfg,html);p.evaluate('hk.emit("checkpoint")')
  for gap in range(s.horizon+1):
   for fid in s.order:
    if (s.a if fid=='a' else s.b)==gap:edit(p,next(f for f in cfg['fields'] if f['id']==fid))
   if gap==s.horizon:break
   if gap==0:load(p,cfg);p.evaluate('multi.mount(CFG)');p.evaluate('hk.phase="hydrated"')
   elif gap==1:p.evaluate('multi.commit()');p.evaluate('hk.phase="committed"')
   else:
    # Mark named phase before the actual user transition, then checkpoint after settling.
    p.evaluate('hk.phase="transitioned"');p.locator('#transition').click();p.evaluate('multi.settle()')
   p.evaluate('hk.emit("checkpoint")')
  p.locator('#submit').click();p.wait_for_function('hk.trace.some(e=>e.type==="ack")')
  run=p.evaluate('RUN');records=json.load(urllib.request.urlopen(ENDPOINT+'/records?run='+run));row['server_records']=records
  if len(records)!=1:raise RuntimeError('missing or duplicate receipt')
  payload=json.loads(records[0]['body']);p.evaluate('(payload)=>hk.emit("receipt",{payload,channel:"application"})',payload)
  row['trace']=p.evaluate('hk.trace');row['oracle']=interpret_form(row['trace'],CONTRACTS[cfg['id']]);row['console']=console;row['page_errors']=errors
  if errors:row['oracle']['status']='inconclusive';row['oracle']['unknown']+=errors
 except Exception as e:row.update(error=str(e),oracle={'status':'inconclusive','failures':[],'unknown':[str(e)],'accepted_edits':0,'blocked_edits':0,'receipts':0})
 finally:p.close()
 row['duration_ms']=(time.perf_counter()-start)*1000;return row

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
 cases=[c for c in CASES if c['id'] in ['MR01','MR03','MV01','MV03']] if args.smoke else CASES
 env={**os.environ,'PORT':'8766'};proc=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL)
 try:
  for _ in range(40):
   try:urllib.request.urlopen(ENDPOINT+'/health',timeout=.2);break
   except Exception:time.sleep(.1)
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox']);html={c['id']:prerender(b,c) for c in cases}
   for strategy in (['smoke'] if args.smoke else ['grid','quotient']):
    start=time.perf_counter();rows=[];reps=1 if strategy!='grid' else 2
    with (ROOT/f'results/phase-grid/multi-{strategy}.jsonl').open('w') as out:
     for rep in range(reps):
      for c in cases:
       commute=independent(EFFECTS,c['handlers']['a'],c['handlers']['b'])
       schedules=pair_quotient(commute) if strategy=='quotient' else pair_grid()
       if args.smoke:schedules=[s for s in schedules if s.horizon in [1,3] and s.a==0 and s.b==0]
       for s in schedules:
        row=execute(b,c,s,html[c['id']],rep);row['source_independent']=commute;out.write(json.dumps(row)+'\n');out.flush();rows.append(row)
       print(strategy,c['id'],rep,dict(collections.Counter(r['oracle']['status'] for r in rows)),flush=True)
    meta={'runs':len(rows),'wall_seconds':time.perf_counter()-start,'browser':b.version,'counts':dict(collections.Counter(r['oracle']['status'] for r in rows)),'receipt_count':sum(len(r.get('server_records',[])) for r in rows),'cases':len(cases),'repeats':reps,'scope':'authored two-field integrations; production runtimes; offline browser prerender; actual local application fetch'}
    (ROOT/f'results/phase-grid/multi-{strategy}.meta.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta),flush=True)
    if any(len(r.get('server_records',[]))!=1 or r['oracle']['status']=='inconclusive' for r in rows):raise RuntimeError('multi-field browser evidence incomplete')
   b.close()
 finally:proc.terminate();proc.wait()
if __name__=='__main__':main()
