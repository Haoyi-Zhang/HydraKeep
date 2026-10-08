#!/usr/bin/env python3
"""Post-design out-of-subset controls: unknown effects retain the complete grid."""
from __future__ import annotations
import pathlib,sys,json,copy,subprocess,time,os,urllib.request,collections
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import run_multi as m
from playwright.sync_api import sync_playwright
from multi_explorer import pair_grid,pair_quotient,independent
SOURCE="""window.HANDLERS={
 computed_a:(s,v)=>{s['a']=v;},
 computed_b:(s,v)=>{s['b']=v;},
 computed_coupled_a:(s,v)=>{s['a']=v;s['b']='seed-b';}
};"""
def main():
 out=ROOT/'results/phase-grid';path=ROOT/'fixtures/multi/fallback-handlers.js';path.write_text(SOURCE)
 effects=json.loads(subprocess.check_output(['node','scripts/extract_effects.mjs',str(path)],cwd=ROOT))
 (out/'fallback-effects.json').write_text(json.dumps(effects,indent=2))
 cases=[]
 for fw,prefix in [('react','MR'),('vue','MV')]:
  for number in ['01','03']:
   cfg=copy.deepcopy(next(c for c in m.CASES if c['id']==prefix+number));cfg['id']=prefix+'F'+number;cfg['split']='post-design-out-of-subset';cfg['handlers']={'a':'computed_a' if number=='01' else 'computed_coupled_a','b':'computed_b'}
   m.CONTRACTS[cfg['id']]=copy.deepcopy(m.CONTRACTS[prefix+number]);cases.append(cfg)
   assert not independent(effects['effects'],cfg['handlers']['a'],cfg['handlers']['b'])
   assert pair_quotient(False)==pair_grid()
 (ROOT/'fixtures/multi/fallback-cases.json').write_text(json.dumps(cases,indent=2))
 # Corpus and expected fallback rule are saved before any new browser outcome.
 original=m.load
 def load(p,cfg):
  original(p,cfg);p.add_script_tag(content=SOURCE)
 m.load=load;m.ENDPOINT='http://127.0.0.1:8768'
 proc=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,env={**os.environ,'PORT':'8768'},stdout=subprocess.DEVNULL)
 t0=time.perf_counter();rows=[]
 try:
  for _ in range(30):
   try:urllib.request.urlopen(m.ENDPOINT+'/health',timeout=.2);break
   except Exception:time.sleep(.1)
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
   with (out/'fallback.jsonl').open('w') as f:
    for cfg in cases:
     html=m.prerender(b,cfg)
     for rep in range(2):
      for s in pair_quotient(False):
       r=m.execute(b,cfg,s,html,rep);r['source_independent']=False;rows.append(r);f.write(json.dumps(r)+'\n');f.flush()
     print(cfg['id'],dict(collections.Counter(r['oracle']['status'] for r in rows)),flush=True)
   b.close()
 finally:proc.terminate();proc.wait()
 summary={'runs':len(rows),'wall_seconds':time.perf_counter()-t0,'statuses':dict(collections.Counter(r['oracle']['status'] for r in rows)),'receipts':sum(len(r.get('server_records',[])) for r in rows),'scope':'4 authored post-design unknown-effect controls; 38 schedules each; 2 repeats; not independent public applications'}
 (out/'fallback.meta.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
