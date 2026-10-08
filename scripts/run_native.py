#!/usr/bin/env python3
"""Native HTTP document navigation, matching server/client components and receipts."""
from __future__ import annotations
import argparse,collections,hashlib,json,os,pathlib,subprocess,sys,time,urllib.request,uuid
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form,signature
from multi_explorer import pair_grid,pair_quotient,independent
CASES=json.loads((ROOT/'fixtures/multi/cases.json').read_text());HISTORICAL=json.loads((ROOT/'fixtures/native/historical-cases.json').read_text());CONTRACTS={**json.loads((ROOT/'fixtures/multi/contracts.json').read_text()),**json.loads((ROOT/'fixtures/native/historical-contracts.json').read_text())};EFFECTS=json.loads((ROOT/'results/phase-grid/effects.json').read_text())['effects']
NATIVE_CONTRACTS=json.loads((ROOT/'fixtures/native/native-submit-contracts.json').read_text())
ENDPOINT='http://127.0.0.1:'+os.environ.get('PORT','8770')
def get(path):return json.load(urllib.request.urlopen(ENDPOINT+path,timeout=8))
def edit(p,f):
 loc=p.locator('[data-hk-field="'+f['id']+'"]')
 if loc.count()==0:p.evaluate('(field)=>hk.emit("edit-absent",{field})',f['id']);return
 if loc.count()!=1:raise RuntimeError('ambiguous target')
 if not loc.is_enabled():p.evaluate('(field)=>hk.emit("edit-blocked",{field})',f['id']);return
 if f['kind']=='checkbox':loc.click()
 elif f['kind']=='select':loc.focus();loc.press('Home');loc.press('ArrowDown');loc.press('Enter')
 else:loc.click();loc.press('ControlOrMeta+A');loc.press_sequentially(f['edit'])
 p.evaluate('(f)=>hk.emit("edit",{field:f.id,requested:f.edit,trusted:hk.last[f.id]?.trusted===true})',f)
def run(browser,cfg,s,mode,tag,rep,ordinal,native=False,adapter=None):
 start=time.perf_counter();p=browser.new_page();p.set_default_timeout(6000);errors=[];console=[]
 p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda m:console.append({'type':m.type,'text':m.text}) if m.type in ['error','warning'] else None)
 run_id=f'native-{mode}-{tag}-{ordinal}';commute=independent(EFFECTS,cfg['handlers']['a'],cfg['handlers']['b'])
 row=dict(case=cfg['id'],framework=cfg['framework'],pattern=cfg['pattern'],schedule=s.as_dict(),mode=mode,version_tag=tag,rep=rep,run=run_id,source_independent=commute,evidence_class='native-ssr-http-navigation',native_submit=native)
 try:
  response=p.goto(f'{ENDPOINT}/native?id={cfg["id"]}&run={run_id}&version={tag}&native={int(native)}',wait_until='load');assert response.status==200
  row['document']=get('/document?run='+run_id);row['url']=p.url;assert row['document']['markup_sha256']==hashlib.sha256(row['document']['markup'].encode()).hexdigest()
  if adapter:p.add_script_tag(content=pathlib.Path(adapter).read_text())
  p.evaluate('hk.emit("checkpoint")')
  for gap in range(s.horizon+1):
   for fid in s.order:
    if (s.a if fid=='a' else s.b)==gap:edit(p,next(f for f in cfg['fields'] if f['id']==fid))
   if gap==s.horizon:break
   if gap==0:
    p.add_script_tag(url=ENDPOINT+'/fixtures/multi/handlers.js');p.add_script_tag(url=ENDPOINT+f'/vendor/native/{cfg["framework"]}-{tag}-{mode}.js')
    if adapter:p.evaluate('initComparison.begin()')
    p.evaluate('multi.mount(CFG)')
    if adapter:p.evaluate('initComparison.end()')
    p.evaluate('hk.phase="hydrated"')
   elif gap==1:p.evaluate('multi.commit()');p.evaluate('hk.phase="committed"')
   else:p.evaluate('hk.phase="transitioned"');p.locator('#transition').click();p.evaluate('multi.settle()')
   p.evaluate('hk.emit("checkpoint")')
  p.locator('#submit').click()
  if not native:p.wait_for_function('hk.trace.some(e=>e.type==="ack")')
  for _ in range(60):
   records=get('/records?run='+run_id)
   if records:break
   time.sleep(.05)
  row['server_records']=records;assert len(records)==1
  if adapter:row['initracer_module']=p.evaluate('initComparison.report()')
  if native:
   from urllib.parse import parse_qs
   body=parse_qs(records[0]['body'],keep_blank_values=True);payload={f['id']:(f['id'] in body if f['kind']=='checkbox' else body.get(f['id'],[None])[0]) for f in cfg['fields']}
  else:payload=json.loads(records[0]['body'])
  channel='native' if native else 'application'
  p.evaluate('(q)=>hk.emit("receipt",q)',dict(payload=payload,channel=channel));row['trace']=p.evaluate('hk.trace');row['contract_channel']=channel;row['oracle']=interpret_form(row['trace'],(NATIVE_CONTRACTS if native else CONTRACTS)[cfg['id']])
  if errors:row['oracle']['unknown']+=errors;row['oracle']['status']='inconclusive'
 except Exception as e:row.update(error=str(e),oracle={'status':'inconclusive','failures':[],'unknown':[str(e)],'accepted_edits':0,'blocked_edits':0,'receipts':0})
 finally:row['console']=console;row['page_errors']=errors;p.close()
 row['duration_ms']=(time.perf_counter()-start)*1000;return row
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');ap.add_argument('--repeats',type=int,default=2);ap.add_argument('--study',choices=['matrix','versions','native-submit','historical'],default='matrix');ap.add_argument('--browser',choices=['chromium','firefox'],default='chromium');ap.add_argument('--baseline-adapter');ap.add_argument('--strategy',choices=['grid','quotient'],default='grid');args=ap.parse_args()
 if args.strategy=='quotient' and args.study!='matrix':raise ValueError('quotient applies to the matrix study')
 out=ROOT/'results/native-integration';out.mkdir(exist_ok=True);proc=subprocess.Popen(['node','src/native-server.mjs'],cwd=ROOT,stdout=subprocess.DEVNULL)
 try:
  for _ in range(50):
   try:urllib.request.urlopen(ENDPOINT+'/health',timeout=.3);break
   except Exception:time.sleep(.1)
  with sync_playwright() as pw:
   opts=dict(headless=True)
   if args.browser=='chromium':opts.update(executable_path=os.environ.get('CHROMIUM_PATH','/tmp/hydrakeep-chromium'),args=['--no-sandbox'])
   b=getattr(pw,args.browser).launch(**opts);rows=[];start=time.perf_counter();ordinal=0
   name=('initracer-module' if args.baseline_adapter else args.study+('-quotient' if args.strategy=='quotient' else ''))+f'-{args.browser}'+('-smoke' if args.smoke else '')
   partial=out/(name+'.'+uuid.uuid4().hex+'.partial.jsonl')
   with partial.open('w') as target:
    for mode in ['development','production']:
     if args.baseline_adapter and mode!='production':continue
     for tag in (['before','after','current'] if args.study in ['versions','historical'] else ['original']):
      for cfg in (HISTORICAL if args.study=='historical' else CASES):
       if args.baseline_adapter and cfg['id'] not in ['MR01','MR02','MR04','MV01','MV02','MV04']:continue
       if args.study=='versions' and cfg['framework']!='vue':continue
       if args.study=='native-submit' and cfg['pattern'] not in ['independent','shadow']:continue
       schedules=pair_quotient(independent(EFFECTS,cfg['handlers']['a'],cfg['handlers']['b'])) if args.strategy=='quotient' else pair_grid()
       if args.study=='historical':
        from multi_explorer import PairSchedule
        schedules=[PairSchedule(1,a,b,'ab' if a<=b else 'ba') for a in [0,1] for b in [0,1]]+[PairSchedule(2,0,0,'ab'),PairSchedule(2,2,2,'ab')]
       if args.study=='native-submit':
        from multi_explorer import PairSchedule
        schedules=[PairSchedule(0,0,0,'ab')]+[s for s in schedules if s.horizon==1]
       if args.smoke:schedules=[s for s in schedules if s.a==0 and s.b==0 and s.order=='ab' and s.horizon in [0,1,3]]
       for rep in range(1 if args.smoke else args.repeats):
        for s in schedules:
         ordinal+=1;row=run(b,cfg,s,mode,tag,rep,ordinal,args.study=='native-submit',args.baseline_adapter);row['browser']=b.version;rows.append(row);target.write(json.dumps(row)+'\n');target.flush()
       print(name,mode,tag,cfg['id'],dict(collections.Counter(r['oracle']['status'] for r in rows)),flush=True)
   meta=dict(runs=len(rows),counts=dict(collections.Counter(r['oracle']['status'] for r in rows)),browser=b.version,browser_engine=args.browser,wall_seconds=time.perf_counter()-start,receipts=sum(len(r.get('server_records',[])) for r in rows),node=subprocess.check_output(['node','--version'],text=True).strip(),python=sys.version,scope='same components native SSR + normal HTTP navigation + same-origin application or native HTTP submission')
   partial.replace(out/(name+'.jsonl'))
   (out/(name+'.meta.json')).write_text(json.dumps(meta,indent=2));b.close();print(json.dumps(meta),flush=True)
   if any(r['oracle']['status']=='inconclusive' for r in rows):raise RuntimeError('incomplete native evidence; retained for diagnosis')
 finally:proc.terminate();proc.wait()
if __name__=='__main__':main()
