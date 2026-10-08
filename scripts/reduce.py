#!/usr/bin/env python3
"""Greedy, real-browser, deletion-1-minimal witnesses in a stated action alphabet."""
import json,pathlib,sys,copy,time,os
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
from run import run_one,prerender,CASES
from explorer import Schedule,ACTIONS,HORIZONS

def main():
    targets=[('R01','H',0,'state-only-loss','hydrated'),('R01','C',0,'dom-loss','committed'),('R15','T',4,'dom-loss','transitioned')]
    results=[];start=time.perf_counter()
    with sync_playwright() as pw:
      browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
      rendered=prerender(browser,[c for c in CASES if c['id'] in {'R01','R15'}])
      with (ROOT/'results/reduction-replays.jsonl').open('w') as raw:
       for cid,h,g,kind,phase in targets:
        cfg=copy.deepcopy(next(c for c in CASES if c['id']==cid));plan=list(ACTIONS[:HORIZONS[h]]);plan.insert(g,'EDIT');original=list(plan);attempts=0
        def test(candidate,cfg2):
            nonlocal attempts
            s=Schedule(h,candidate.index('EDIT'));r=run_one(browser,cfg2,s,rendered,actions=[x for x in candidate if x!='EDIT'])
            ok=r['oracle']['status']=='violation' and r['oracle']['accepted_edits']==1 and any(f['kind']==kind and f['phase']==phase for f in r['oracle']['failures'])
            attempts+=1;raw.write(json.dumps(dict(candidate=candidate,edit=cfg2['edit'],preserves_target=ok,observation=r))+'\n');raw.flush();return ok,r
        ok,original_run=test(plan,cfg);assert ok
        changed=True
        while changed:
            changed=False
            for i,a in enumerate(plan):
                if a=='EDIT':continue
                candidate=plan[:i]+plan[i+1:];ok,r=test(candidate,cfg)
                if ok:plan=candidate;changed=True;break
        old_edit=cfg['edit'];cfg2=copy.deepcopy(cfg);cfg2['edit']=str(cfg2['edit'])[0]
        ok,r=test(plan,cfg2)
        if ok:cfg=cfg2
        ok,final=test(plan,cfg);assert ok
        results.append(dict(case=cid,horizon=h,target_kind=kind,target_phase=phase,original_actions=original,reduced_actions=plan,original_edit=old_edit,reduced_edit=cfg['edit'],attempts=attempts,final=final,minimality='deletion-1-minimal controller actions with edit and final submit retained; single-character nonempty string tested; not globally minimal JS/program input'))
      browser.close()
    (ROOT/'results/reductions.json').write_text(json.dumps(dict(wall_seconds=time.perf_counter()-start,witnesses=results),indent=2))
    print(json.dumps([{k:v for k,v in x.items() if k!='final'} for x in results],indent=2))
if __name__=='__main__':main()
