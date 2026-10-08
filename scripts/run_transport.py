#!/usr/bin/env python3
"""Real-browser loopback receipts; offline initial documents; no policy changes."""
import json,sys,time,subprocess,urllib.request,collections,pathlib,os
import run as legacy
from explorer import grid,quotient,Schedule
from oracle import same_value
from playwright.sync_api import sync_playwright
ROOT=legacy.ROOT;ENDPOINT='http://127.0.0.1:8765'
legacy.OBSERVER=(ROOT/'src/observer-transport.js').read_text()
old_init=legacy.initialize
counter=0

def initialize(p,cfg,markup=''):
 global counter
 counter+=1
 old_init(p,cfg,markup)
 p.evaluate('(v)=>{window.ENDPOINT=v.url;window.RUN=v.run;window.OBSERVATION_ONLY=false}',{'url':ENDPOINT,'run':f'transport-{counter}'})
legacy.initialize=initialize

def signature(r):
 o=r['oracle'];return [o['status'],sorted({(f['kind'],f['phase']) for f in o['failures']}),o['accepted_edits'],o['blocked_edits']]

def execute(browser,cfg,s,rendered,rep):
 # Keep the page alive until server acknowledgments; legacy run_one closes it.
 # Hooks below intercept its final trace read, awaiting actual endpoint receipt.
 records=[];new_page=browser.new_page
 def create(*args,**kw):
  p=new_page(*args,**kw);ev=p.evaluate
  def evaluate(expr,*args,**kw):
   if expr=='__hk.trace':
    p.wait_for_function('__hk.trace.some(e=>e.type==="application-submitted"||e.type==="native-bridge-submitted")',timeout=4000)
    run=ev('window.RUN');rec=json.load(urllib.request.urlopen(ENDPOINT+'/records?run='+run));records.extend(rec)
   return ev(expr,*args,**kw)
  p.evaluate=evaluate;return p
 browser.new_page=create
 try:r=legacy.run_one(browser,cfg,s,rendered,rep)
 finally:browser.new_page=new_page
 r['evidence_class']='offline-real-chromium-with-loopback-receipt';r['server_records']=records
 channel=legacy.CONTRACTS[cfg['id']]['channel'];r['transport']='application-fetch' if channel=='application-intent' else 'instrumented-native-FormData-forwarding'
 if len(records)!=1:
  r['receipt_check']={'status':'inconclusive','reason':f'expected one server receipt, found {len(records)}'}
 else:
  rec=records[0]
  if rec['contentType'].startswith('application/json'):value=json.loads(rec['body']).get('value')
  else:
   from urllib.parse import parse_qs
   body=parse_qs(rec['body'],keep_blank_values=True);value=('value' in body) if cfg['kind']=='checkbox' else body.get('value',[None])[0]
  expected=next((e.get('submittedValue') if channel=='application-intent' else e.get('serializedValue') for e in reversed(r.get('trace',[])) if e['type'] in (['application-submitted'] if channel=='application-intent' else ['native-serialization'])),None)
  r['receipt_check']={'status':'match' if same_value(value,expected) else 'mismatch','receivedValue':value,'observedConsumerValue':expected}
 return r

def main():
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--smoke',action='store_true');args=a.parse_args()
 proc=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,stdout=subprocess.DEVNULL)
 try:
  for _ in range(40):
   try:urllib.request.urlopen(ENDPOINT+'/health',timeout=.3);break
   except Exception:time.sleep(.1)
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
   cases=legacy.CASES if not args.smoke else [c for c in legacy.CASES if c['id'] in ['R01','R05','V01','V12']]
   rend=legacy.prerender(b,cases)
   old={(r['case'],r['horizon'],r['gap'],r['rep']):r for r in map(json.loads,(ROOT/'results/grid.jsonl').read_text().splitlines())}
   for name,schedules,reps in [('transport-grid',grid(),2),('transport-quotient',quotient(),1)]:
    if args.smoke:name='transport-smoke';schedules=[Schedule('H',0)];reps=1
    start=time.perf_counter();rows=[]
    with (ROOT/f'results/phase-grid/{name}.jsonl').open('w') as out:
     for rep in range(reps):
      for cfg in cases:
       for s in schedules:
        row=execute(b,cfg,s,rend,rep);row['legacy_signature_agreement']=signature(row)==signature(old[(cfg['id'],s.horizon,s.gap,rep)])
        out.write(json.dumps(row)+'\n');out.flush();rows.append(row)
       print(name,cfg['id'],rep,dict(collections.Counter(r['oracle']['status'] for r in rows)),flush=True)
    meta={'runs':len(rows),'wall_seconds':time.perf_counter()-start,'browser':b.version,'counts':dict(collections.Counter(r['oracle']['status'] for r in rows)),'receipts':sum(len(r['server_records']) for r in rows),'receipt_checks':dict(collections.Counter(r['receipt_check']['status'] for r in rows)),'legacy_disagreements':sum(not r['legacy_signature_agreement'] for r in rows),'transport_counts':dict(collections.Counter(r['transport'] for r in rows)),'scope':'offline browser-prerender; actual loopback fetch; native FormData uses disclosed bridge'}
    (ROOT/f'results/phase-grid/{name}.meta.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta),flush=True)
    if any(r['receipt_check']['status']!='match' or r['oracle']['status']=='inconclusive' or r.get('page_errors') for r in rows):raise RuntimeError('browser transport evidence incomplete or mismatched')
    if args.smoke:break
   b.close()
 finally:proc.terminate();proc.wait()
if __name__=='__main__':main()
