#!/usr/bin/env python3
"""Post-design adversarial controls, separate from development and holdout corpora."""
from __future__ import annotations
import pathlib,sys,json,time,os,subprocess,urllib.request,copy,collections
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import run_multi as m
from playwright.sync_api import sync_playwright
from form_oracle import interpret_form

def run(b,cfg,html,steps,rep,drop=False):
 p=b.new_page();t0=time.perf_counter();row={'case':cfg['id'],'framework':cfg['framework'],'steps':steps,'rep':rep,'classification':'post-design-authored-adversarial-control','seeded_receipt_drop':drop}
 try:
  m.init(p,cfg,html);p.evaluate('hk.emit("checkpoint")')
  for step in steps:
   if step=='H':m.load(p,cfg);p.evaluate('multi.mount(CFG)');p.evaluate('hk.phase="hydrated";hk.emit("checkpoint")')
   elif step=='C':p.evaluate('multi.commit()');p.evaluate('hk.phase="committed";hk.emit("checkpoint")')
   elif step=='T':p.evaluate('hk.phase="transitioned"');p.locator('#transition').click();p.evaluate('multi.settle()');p.evaluate('hk.emit("checkpoint")')
   else:
    f=copy.deepcopy(next(f for f in cfg['fields'] if f['id']==step[0]));
    if len(step)>1:f['edit']='second-'+f['id']
    m.edit(p,f)
  if drop:p.evaluate('()=>{const old=hk.post;hk.post=(payload)=>old({...payload,a:CFG.fields[0].initial})}')
  p.locator('#submit').click();p.wait_for_function('hk.trace.some(e=>e.type==="ack")');run=p.evaluate('RUN');records=json.load(urllib.request.urlopen(m.ENDPOINT+'/records?run='+run));assert len(records)==1
  payload=json.loads(records[0]['body']);p.evaluate('(payload)=>hk.emit("receipt",{payload,channel:"application"})',payload);trace=p.evaluate('hk.trace')
  c=copy.deepcopy(m.CONTRACTS['MR04' if cfg['framework']=='react' else 'MV04']);row.update(trace=trace,server_records=records,contracts=c,oracle=interpret_form(trace,c),ablations={a:interpret_form(trace,c,ablation=a) for a in ['dom-only','strict-node','global-reset']})
 except Exception as e:row.update(error=str(e),oracle={'status':'inconclusive'})
 finally:p.close()
 row['duration_ms']=(time.perf_counter()-t0)*1000;return row

def main():
 # Other main studies use 8765/8766; do not share receiver state.
 m.ENDPOINT='http://127.0.0.1:8767';proc=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,env={**os.environ,'PORT':'8767'},stdout=subprocess.DEVNULL);time.sleep(.4)
 rows=[]
 try:
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
   for fw,prefix in [('react','MR'),('vue','MV')]:
    c=copy.deepcopy(next(c for c in m.CASES if c['id']==prefix+'03'));c['id']=prefix+'-consumer-conflict';c['bindings']={'a':'uncontrolled','b':'uncontrolled'};c['handlers']={'a':'hidden_a','b':'hidden_b'}
    html=m.prerender(b,c)
    for rep in range(2):
     for order in [('a','b'),('b','a')]:rows.append(run(b,c,html,['H',*order],rep))
    c=copy.deepcopy(next(c for c in m.CASES if c['id']==prefix+'04'));c['id']=prefix+'-second-epoch';html=m.prerender(b,c)
    for rep in range(2):
     for drop in [False,True]:rows.append(run(b,c,html,['H','a','b','T','a2'],rep,drop))
    c=copy.deepcopy(next(c for c in m.CASES if c['id']==prefix+'06'));c['id']=prefix+'-preserving-replacement';c['bindings']={'a':'controlled','b':'controlled'};c['adopt']=True;html=m.prerender(b,c)
    for rep in range(2):rows.append(run(b,c,html,['a','b','H','C','T'],rep))
   b.close()
 finally:proc.terminate();proc.wait()
 out=ROOT/'results/phase-grid/challenges.jsonl';out.write_text(''.join(json.dumps(r)+'\n' for r in rows));summary={'runs':len(rows),'statuses':dict(collections.Counter(r['oracle']['status'] for r in rows)),'receipts':sum(len(r.get('server_records',[])) for r in rows)};(out.with_suffix('.meta.json')).write_text(json.dumps(summary,indent=2));print(json.dumps(summary));
 for r in rows:print(r['case'],r['steps'],r['rep'],r['seeded_receipt_drop'],r['oracle']['status'],r.get('oracle',{}).get('failures'),r.get('error',''))
if __name__=='__main__':main()
