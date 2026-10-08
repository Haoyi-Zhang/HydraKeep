#!/usr/bin/env python3
"""Execute original HTML/JS instrumentation and analysis runtime on local controls."""
import argparse,collections,json,os,pathlib,subprocess,sys,time,urllib.request
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form
def wait(p,expression):
 for _ in range(120):
  if p.evaluate(expression):return
  time.sleep(.05)
 raise RuntimeError('readiness timeout: '+expression)
def click(p,identifier):
 q=p.evaluate('(id)=>{const r=document.getElementById(id).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}}',identifier)
 p.mouse.click(q['x'],q['y'])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--tool-dir',required=True);ap.add_argument('--modes',nargs='+',choices=['none','observation','adverse'],default=['none','observation']);args=ap.parse_args();out=ROOT/'results/native-integration';proc=subprocess.Popen(['node','control-server.cjs'],cwd=args.tool_dir);rows=[]
 try:
  for _ in range(40):
   try:urllib.request.urlopen('http://127.0.0.1:8776/health',timeout=.2);break
   except Exception:time.sleep(.1)
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/tmp/hydrakeep-chromium'),headless=True,args=['--no-sandbox'])
   for mode in args.modes:
    for case in ['overwrite','shadow','adopt','reset']:
     for rep in range(2):
      p=b.new_page();p.set_default_timeout(6000);p.add_init_script((ROOT/'src/multi-observer.js').read_text()+"\ndocument.addEventListener('click',e=>{if(e.target.id==='reset')hk.resetTrusted=e.isTrusted;},true);");held=[];errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.route('**/boot.js*',lambda r:held.append(r));run=f'control-{mode}-{case}-{rep}';row=dict(run=run,case=case,mode=mode,rep=rep,tool_commit='b5f1c0bffd118008c64b30ec3723b2443b6d95cf',scope='original instrumentation and runtime on four authored vanilla controls; custom HTTP/Playwright driver; no modern-framework tool benchmark')
      try:
       p.goto(f'http://127.0.0.1:8776/?case={case}&run={run}&mode={mode}',wait_until='commit');wait(p,'document.getElementById("a")!==null');click(p,'a');p.keyboard.press('ControlOrMeta+A');p.keyboard.type('toy')
       p.evaluate('hk.emit("edit",{field:"a",requested:"toy",trusted:hk.last.a?.trusted===true})')
       for r in held:r.continue_()
       wait(p,'window.ready===true');p.evaluate('hk.phase="hydrated";hk.emit("checkpoint")')
       if case=='reset':click(p,'reset');p.evaluate('hk.emit("transition",{name:"reset",trusted:hk.resetTrusted===true});hk.emit("checkpoint")')
       click(p,'submit');records=[]
       for _ in range(40):
        records=json.load(urllib.request.urlopen('http://127.0.0.1:8776/records?run='+run))
        if records:break
        time.sleep(.05)
       assert len(records)==1
       row['server_records']=records;payload=json.loads(records[0]['body']);p.evaluate('(payload)=>hk.emit("receipt",{payload,channel:"application"})',payload);row['trace']=p.evaluate('hk.trace');row['oracle']=interpret_form(row['trace'],{'a':{'channel':'application','resets':['reset']}})
       if mode!='none':row['initracer']=p.evaluate('({report:initRacer.getReport(),summary:initRacer.getSummary()})')
       row['page_errors']=errors
      except Exception as e:row.update(error=str(e),page_errors=errors)
      finally:p.close()
      rows.append(row);print(mode,case,rep,row.get('error','ok'),flush=True)
   b.close()
  (out/'initracer-controls.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
  if any('error' in r or r['page_errors'] for r in rows):raise RuntimeError('InitRacer control evidence incomplete')
 finally:proc.terminate();proc.wait()
if __name__=='__main__':main()
