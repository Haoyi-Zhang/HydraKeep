#!/usr/bin/env python3
"""Licensed Next.js/RHF example: real Next prerender and deferred chunk hydration."""
from __future__ import annotations
import argparse,collections,hashlib,itertools,json,os,pathlib,signal,subprocess,sys,time,urllib.request
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form
APP=ROOT/'fixtures/external/next-rhf';BASE='http://127.0.0.1:8771'
STAMP=str(time.time_ns())
OBSERVER='''(()=>{
 const nodes=new WeakMap();let n=0;window.hk={trace:[],phase:'pre',last:{}};
 hk.read=e=>e.type==='checkbox'?e.checked:e.value;
 hk.fields=()=>[...document.querySelectorAll('input[name]')].map(e=>{if(!nodes.has(e))nodes.set(e,++n);return{id:e.name,node:nodes.get(e),value:hk.read(e),disabled:e.disabled,readOnly:e.readOnly};});
 hk.emit=(type,detail={})=>hk.trace.push({type,...detail,phase:hk.phase,fields:hk.fields(),ms:performance.now()});
 for(const name of ['input','change'])document.addEventListener(name,e=>{if(e.target.matches('input[name]'))hk.last[e.target.name]={trusted:e.isTrusted,value:hk.read(e.target)};},true);
 document.addEventListener('submit',e=>{hk.phase='submit';hk.emit('consume',{trusted:e.isTrusted});},true);
})();'''
def execute(b,gaps,mode,rep,ordinal):
 p=b.new_page();p.set_default_timeout(10000);p.add_init_script(OBSERVER);held=[];released=False;errors=[]
 p.on('pageerror',lambda e:errors.append(str(e)))
 def gate(route):
  if released:route.continue_()
  else:held.append(route)
 p.route('**/_next/static/**/*.js*',gate)
 run=f'public-{mode}-{STAMP}-{ordinal}';row=dict(run=run,mode=mode,gaps=dict(zip(['username','password','remember'],gaps)),rep=rep,case='next-rhf-example',evidence_class='licensed-independent-next-example-native-prerender',browser=b.version)
 try:
  r=p.goto(BASE+'/?run='+run,wait_until='commit');p.wait_for_selector('#username',state='attached');body=r.text();row['document_sha256']=hashlib.sha256(body.encode()).hexdigest();row['native_markup']=all(x in body for x in ['id="username"','id="password"','__NEXT_DATA__']);assert row['native_markup']
  p.evaluate('hk.emit("checkpoint")')
  for gap in [0,1]:
   for field,wanted in [('username','toy-user'),('password','toy-pass'),('remember',True)]:
    if row['gaps'][field]!=gap:continue
    loc=p.locator('#'+field)
    if not loc.is_visible():p.evaluate('(field)=>hk.emit("edit-blocked",{field,reason:"not visible"})',field);continue
    if field=='remember':loc.click()
    else:loc.click();loc.press('ControlOrMeta+A');loc.press_sequentially(wanted)
    p.evaluate('(x)=>hk.emit("edit",{field:x.field,requested:x.wanted,trusted:hk.last[x.field]?.trusted===true})',dict(field=field,wanted=wanted))
   if gap==0:
    released=True
    for route in held:route.continue_()
    held.clear();p.wait_for_function('window.__hkReady===true');p.evaluate('hk.phase="hydrated";hk.emit("checkpoint")')
  if p.evaluate('hk.trace.some(e=>e.type==="edit-blocked")'):
   row['trace']=p.evaluate('hk.trace');row['availability_screen']='at least one requested early edit was unavailable';row['oracle']={'status':'not-evaluated','reason':'profile unavailable; no submission attempted'};return row
  p.locator('button[type="submit"]').click();records=[]
  for _ in range(80):
   records=json.load(urllib.request.urlopen(BASE+'/api/receipt?run='+run,timeout=3))
   if records:break
   time.sleep(.05)
  assert len(records)==1,'missing/duplicate callback receipt'
  row['server_records']=records;p.evaluate('(payload)=>{hk.phase="success";hk.emit("checkpoint");hk.emit("receipt",{payload,channel:"application"})}',records[0]['payload'])
  row['trace']=p.evaluate('hk.trace');row['oracle']=interpret_form(row['trace'],{f:{'channel':'application'} for f in ['username','password','remember']});row['success_text']=p.locator('h2').inner_text();row['form_removed']=p.locator('form').count()==0
  if errors:row['oracle']['status']='inconclusive';row['oracle']['unknown']+=errors
 except Exception as e:row.update(error=str(e),oracle={'status':'inconclusive','failures':[],'unknown':[str(e)],'accepted_edits':0,'blocked_edits':0,'receipts':0})
 finally:row['page_errors']=errors;p.close()
 return row
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['development','production'],default='production');ap.add_argument('--smoke',action='store_true');args=ap.parse_args();out=ROOT/'results/native-integration';out.mkdir(exist_ok=True)
 log=(out/f'public-{args.mode}-server.log').open('w');proc=subprocess.Popen(['node','node_modules/next/dist/bin/next','dev' if args.mode=='development' else 'start','-p','8771','-H','127.0.0.1'],cwd=APP,env={**os.environ,'NEXT_TELEMETRY_DISABLED':'1'},stdout=log,stderr=log,start_new_session=True)
 try:
  ready=False
  for _ in range(160):
   if proc.poll() is not None:raise RuntimeError('Next server exited; inspect server log')
   try:urllib.request.urlopen(BASE+'/',timeout=2);break
   except Exception:time.sleep(.2)
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/tmp/hydrakeep-chromium'),headless=True,args=['--no-sandbox']);rows=[];ordinal=0
   name=f'public-{args.mode}'+('-smoke' if args.smoke else '')
   with (out/(name+'.jsonl')).open('w') as f:
    for rep in range(1 if args.smoke else 2):
     for gaps in ([(0,0,0),(1,1,1)] if args.smoke else itertools.product([0,1],repeat=3)):
      ordinal+=1;row=execute(b,gaps,args.mode,rep,ordinal);rows.append(row);f.write(json.dumps(row)+'\n');f.flush();print(name,gaps,row['oracle']['status'],row.get('error',''),flush=True)
   meta=dict(runs=len(rows),counts=dict(collections.Counter(r['oracle']['status'] for r in rows)),receipts=sum(len(r.get('server_records',[])) for r in rows),scope='one independent MIT Next.js example; callback-only receipt and readiness instrumentation; no production users or upstream defect claim');(out/(name+'.meta.json')).write_text(json.dumps(meta,indent=2));b.close()
   if any(r['oracle']['status']=='inconclusive' for r in rows):raise RuntimeError('public evidence incomplete')
 finally:os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10);log.close()
if __name__=='__main__':main()
