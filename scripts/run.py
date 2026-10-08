#!/usr/bin/env python3
"""Bounded real-Chromium evaluation. No browser networking in observed runs."""
from __future__ import annotations
import argparse,json,pathlib,sys,time,os,platform,subprocess,resource
from importlib.metadata import version
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from oracle import interpret
from explorer import ACTIONS,HORIZONS,grid,quotient
CASES=json.loads((ROOT/'fixtures/cases.json').read_text());CONTRACTS=json.loads((ROOT/'fixtures/contracts.json').read_text())
OBSERVER=(ROOT/'src/observer.js').read_text()
VENDORS={f:(ROOT/f'vendor/{f}-{v}.production.js').read_text() for f,v in [('react','19.1.1'),('vue','3.5.13')]}
ADAPTERS={f:(ROOT/f'src/{f}-adapter.js').read_text() for f in VENDORS}

def load(page,cfg):
    page.add_script_tag(content=VENDORS[cfg['framework']]);page.add_script_tag(content=ADAPTERS[cfg['framework']])

def initialize(page,cfg,markup=''):
    page.set_default_timeout(4000)
    page.set_content('<!doctype html><html><head><meta charset="utf-8"><style>body{font:18px sans-serif;padding:20px}input,textarea,select,button{font:inherit;margin:8px;padding:6px}</style></head><body><p id="unrelated">Independent region</p><div id="root">'+markup+'</div></body></html>')
    page.evaluate('(cfg)=>{window.CFG=cfg;window.RUN="local";window.OBSERVATION_ONLY=true;}',cfg)
    page.add_script_tag(content=OBSERVER)

def prerender(browser,cases):
    rendered={}
    for cfg in cases:
        p=browser.new_page();initialize(p,cfg);load(p,cfg);p.evaluate('adapter.mount(CFG,true)')
        # Serialize current native defaults, as a browser-based static prerenderer.
        p.evaluate('''() => {for(const el of document.querySelectorAll('[data-hk-field]')){
          if(el.type==='checkbox'){el.toggleAttribute('checked',el.checked);}
          else if(el.tagName==='TEXTAREA')el.textContent=el.value;
          else if(el.tagName==='SELECT'){for(const o of el.options)o.toggleAttribute('selected',o.selected);}
          else el.setAttribute('value',el.value);
        }}''')
        rendered[cfg['id']]={'html':p.locator('#root').inner_html(),'origin':cfg['framework']+' browser-prerender; not framework server renderer','initial':p.evaluate('__hk.snapshot()')}
        p.close()
    return rendered

def edit(page,cfg):
    loc=page.locator('[data-hk-field="toy-field"]')
    if loc.count()!=1:
        page.evaluate('__hk.emit("edit-absent")');return
    if not loc.is_enabled() or loc.get_attribute('readonly') is not None:
        page.evaluate('__hk.emit("edit-blocked")');return
    if cfg['kind']=='checkbox':
        if loc.is_checked()!=cfg['edit']:loc.click()
    elif cfg['kind']=='select':
        loc.focus();loc.press('Home');loc.press('ArrowDown');loc.press('Enter')
    else:
        loc.click();loc.press('ControlOrMeta+A');loc.press_sequentially(cfg['edit'])
    page.evaluate('(v)=>__hk.emit("edit-complete",{requested:v})',cfg['edit'])

def run_one(browser,cfg,s,rendered,rep=0,actions=None):
    start=time.perf_counter();p=browser.new_page();console=[];errors=[]
    p.on('console',lambda m:console.append({'type':m.type,'text':m.text}) if m.type in ['warning','error'] else None)
    p.on('pageerror',lambda e:errors.append(str(e)))
    row={'case':cfg['id'],'framework':cfg['framework'],'split':cfg['split'],'horizon':s.horizon,'gap':s.gap,'rep':rep,'evidence_class':'offline-real-chromium','transport':'intent-and-serialization-only'}
    try:
        initialize(p,cfg,rendered[cfg['id']]['html']);p.evaluate('__hk.emit("checkpoint")')
        plan=list(ACTIONS[:HORIZONS[s.horizon]]) if actions is None else actions
        for i in range(len(plan)+1):
            if i==s.gap:edit(p,cfg)
            if i==len(plan):break
            a=plan[i]
            if a=='load':load(p,cfg);p.evaluate('__hk.phase="loaded";__hk.emit("checkpoint")')
            elif a=='hydrate':p.evaluate('adapter.mount(CFG)');p.evaluate('__hk.phase="hydrated";__hk.emit("checkpoint")')
            elif a=='commit':p.evaluate('adapter.commit()');p.evaluate('__hk.phase="committed";__hk.emit("checkpoint")')
            elif a=='transition':
                if cfg['design']=='reset':p.locator('#reset').click();p.evaluate('adapter.settle ? adapter.settle() : Promise.resolve()')
                else:p.evaluate('adapter.transition(CFG)')
                p.evaluate('__hk.phase="transitioned";__hk.emit("checkpoint")')
            elif a=='noise':p.evaluate('__hk.noise()')
            else:raise ValueError(a)
        p.evaluate('__hk.emit("checkpoint")');p.locator('#submit').click()
        p.wait_for_function('__hk.trace.some(e=>e.type==="native-serialization")')
        p.evaluate('__hk.emit("checkpoint")')
        row['trace']=p.evaluate('__hk.trace');row['oracle']=interpret(row['trace'],CONTRACTS[cfg['id']]);row['console']=console;row['page_errors']=errors
        if errors:row['oracle']['status']='inconclusive';row['oracle']['inconclusive']+=errors
    except Exception as e:
        row.update(error=str(e),console=console,page_errors=errors,oracle={'status':'inconclusive','failures':[],'inconclusive':[str(e)],'accepted_edits':0,'blocked_edits':0,'intentional_replacements':0})
    finally:p.close()
    row['duration_ms']=(time.perf_counter()-start)*1000
    return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');ap.add_argument('--ids');ap.add_argument('--strategy',choices=['grid','quotient'],default='grid');ap.add_argument('--repeats',type=int,default=1);ap.add_argument('--output',default='results/raw.jsonl');args=ap.parse_args()
    if args.repeats < 1:ap.error('--repeats must be a positive integer')
    if args.smoke and args.ids:ap.error('--smoke and --ids cannot be combined')
    if args.ids:
        requested=args.ids.split(',');unknown=set(requested)-{c['id'] for c in CASES}
        if unknown:ap.error('Unknown configuration ID(s): '+','.join(sorted(unknown)))
        if len(requested)!=len(set(requested)):ap.error('Configuration IDs must be unique')
    cases=CASES
    if args.ids:cases=[c for c in cases if c['id'] in args.ids.split(',')]
    if args.smoke:cases=[c for c in cases if c['id'] in ['R01','R05','R07','V01','V06','V15']]
    schedules=grid() if args.strategy=='grid' else quotient()
    if args.smoke:schedules=[s for s in schedules if s.gap==0 and s.horizon in ['H','C']]
    dest=ROOT/args.output;dest.parent.mkdir(parents=True,exist_ok=True);start=time.perf_counter();counts={}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        rendered=prerender(browser,cases)
        rendpath=ROOT/'fixtures/rendered.json';previous=json.loads(rendpath.read_text()) if rendpath.exists() else {};previous.update(rendered);rendpath.write_text(json.dumps(previous,indent=2))
        with dest.open('w') as out:
            for rep in range(args.repeats):
                for cfg in cases:
                    for s in schedules:
                        row=run_one(browser,cfg,s,rendered,rep);out.write(json.dumps(row)+'\n');out.flush();counts[row['oracle']['status']]=counts.get(row['oracle']['status'],0)+1
                    print(f'{cfg["id"]} repeat {rep}: {counts}',flush=True)
        meta={'wall_seconds':time.perf_counter()-start,'browser':browser.version,'playwright':version('playwright'),'node':subprocess.check_output(['node','--version'],text=True).strip(),'python':platform.python_version(),'system':platform.platform(),'counts':counts,'configurations':len(cases),'schedules_per_configuration':len(schedules),'repeats':args.repeats,'cpu_quota':pathlib.Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_limit':pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip(),'self_max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'children_max_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'browser_transport':'offline set_content/add_script_tag; localhost navigation blocked by managed policy','framework_modes':{'react':'19.1.1 production','vue':'3.5.13 production'},'holdout':'R14,R15,V14,V15; authored combinations, not independent applications'}
        browser.close()
    dest.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
