#!/usr/bin/env python3
"""Bounded two-consumption study; actual Chromium actions and HTTP receipts.

This supplementary profile uses offline browser-prerendered documents, explicitly
not native SSR or normal HTTP document navigation. Only receiver request bodies
become receipt events. Two dispatch orders are controlled; no wall-time race claim.
"""
from __future__ import annotations
import argparse, collections, itertools, json, os, pathlib, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from transaction_oracle import interpret_transactions
from transaction_spec import specify
CASES=json.loads((ROOT/'fixtures/transactions/cases.json').read_text())
CONTRACTS=json.loads((ROOT/'fixtures/transactions/contracts.json').read_text())
ENDPOINT='http://127.0.0.1:8774'


def init(page,cfg,run,markup=''):
    page.set_default_timeout(5000)
    page.set_content('<!doctype html><html><head><meta charset="utf-8"><style>body{padding:20px}input,button{font-size:18px;margin:8px}</style></head><body><div id="root">'+markup+'</div></body></html>')
    page.evaluate('(o)=>Object.assign(window,o)',dict(CFG=cfg,RUN=run,ENDPOINT=ENDPOINT))
    page.add_script_tag(content=(ROOT/'src/transaction-observer.js').read_text())


def load(page,cfg):
    version='19.1.1' if cfg['framework']=='react' else '3.5.13'
    page.add_script_tag(content=(ROOT/f'vendor/{cfg["framework"]}-{version}.production.js').read_text())
    page.add_script_tag(content=(ROOT/f'src/transaction-{cfg["framework"]}.js').read_text())


def prerender(browser,cfg):
    page=browser.new_page()
    try:
        init(page,cfg,'prerender');load(page,cfg);page.evaluate('txApp.mount(CFG,true)')
        page.evaluate('''()=>{for(const e of document.querySelectorAll('[data-hk-field]')) e.setAttribute('value',e.value)}''')
        return page.locator('#root').inner_html()
    finally:page.close()


def edit(page,fid,value):
    loc=page.locator('[data-hk-field="'+fid+'"]')
    if loc.count()!=1:raise RuntimeError('Non-unique edit target: '+fid)
    if not loc.is_enabled() or loc.get_attribute('readonly') is not None:
        page.evaluate('(field)=>tx.emit("edit-blocked",{field})',fid);return
    loc.click();loc.press('ControlOrMeta+A');loc.press_sequentially(value)
    page.evaluate('([field,requested])=>tx.emit("edit",{field,requested,trusted:tx.last[field]?.trusted===true})',[fid,value])


def execute(browser,cfg,html,gap,order,rep,run):
    started=time.perf_counter();page=browser.new_page();errors=[];warnings=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:warnings.append(m.text) if m.type in ['warning','error'] else None)
    row=dict(case=cfg['id'],framework=cfg['framework'],pattern=cfg['pattern'],
             gap=gap,dispatch_order=list(order),rep=rep,run=run,
             evidence_class='offline-browser-prerender-real-hydration-loopback-http',server_records=[])
    try:
        init(page,cfg,run,html);page.evaluate('tx.emit("checkpoint")')
        if gap=='post':
            load(page,cfg);page.evaluate('txApp.mount(CFG)');page.evaluate('tx.phase="hydrated";tx.emit("checkpoint")')
        edit(page,'a','toy-a1');edit(page,'b','toy-b1')
        if gap=='pre':
            load(page,cfg);page.evaluate('txApp.mount(CFG)');page.evaluate('tx.phase="hydrated";tx.emit("checkpoint")')
        page.locator('#submit').click();page.evaluate('tx.settle()');page.evaluate('tx.phase="after-first-consume";tx.emit("checkpoint")')
        if cfg['pattern'] in ['epoch-reset','stale-after-reset']:
            page.locator('#reset-a').click();page.evaluate('tx.settle()');page.evaluate('tx.emit("checkpoint")')
        fid='b' if cfg['pattern'] in ['scoped-submit','overbroad-clear'] else 'a'
        edit(page,fid,'toy-'+fid+'2')
        page.locator('#submit').click();page.evaluate('tx.settle()');page.evaluate('tx.phase="after-second-consume";tx.emit("checkpoint")')
        for tid in order:
            page.evaluate('(id)=>tx.phase="receipt-"+id',tid)
            consumer=page.evaluate('(id)=>tx.release(id)',tid)
            records=json.load(urllib.request.urlopen(ENDPOINT+'/records?run='+run+':'+tid,timeout=5))
            if len(records)!=1:raise RuntimeError('Nonunique server receipt: '+tid)
            record=records[0];record.update(transaction=tid,consumer=consumer)
            row['server_records'].append(record)
            payload=json.loads(record['body'])
            page.evaluate('(o)=>tx.emit("receipt",o)',dict(transaction=tid,consumer=consumer,channel='application',payload=payload))
        row['trace']=page.evaluate('tx.trace')
        row['oracle']=interpret_transactions(row['trace'],CONTRACTS[cfg['id']])
        row['reference']=specify(row['trace'],CONTRACTS[cfg['id']])
        row['page_errors']=errors;row['console']=warnings
        if errors:raise RuntimeError('Browser errors: '+repr(errors))
    except Exception as exc:
        row['error']=str(exc)
        row.setdefault('trace',page.evaluate('window.tx?.trace || []'))
        row['oracle']=dict(status='inconclusive',unknown=[str(exc)],failures=[])
    finally:page.close()
    row['duration_ms']=(time.perf_counter()-started)*1000
    return row


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--repeats',type=int,default=2)
    parser.add_argument('--output',default=None);args=parser.parse_args()
    if args.repeats<1:raise SystemExit('repeats must be positive')
    output=ROOT/(args.output or ('results/transactions/transactions-smoke.jsonl' if args.smoke else 'results/transactions/transactions.jsonl'));output.parent.mkdir(parents=True,exist_ok=True)
    cfgs=CASES if not args.smoke else [c for c in CASES if c['pattern'] in ['snapshot','late-read','scoped-submit','overbroad-clear']]
    proc=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,env={**os.environ,'PORT':'8774'},stdout=subprocess.DEVNULL)
    rows=[];start=time.perf_counter()
    try:
        for _ in range(50):
            if proc.poll() is not None:
                raise RuntimeError('Local receiver exited; check that port 8774 is available')
            try:
                with urllib.request.urlopen(ENDPOINT+'/health',timeout=.2) as r:
                    if r.read()==b'ok':break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Local receiver unavailable')
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            rendered={c['id']:prerender(browser,c) for c in cfgs}
            with output.open('w') as stream:
                combinations=itertools.product(range(1 if args.smoke else args.repeats),cfgs,
                      ['pre'] if args.smoke else ['pre','post'],[('t2','t1')] if args.smoke else [('t1','t2'),('t2','t1')])
                for i,(rep,cfg,gap,order) in enumerate(combinations,1):
                    row=execute(browser,cfg,rendered[cfg['id']],gap,order,rep,'transaction-'+str(i))
                    rows.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
                    if args.smoke or i%8==0:print(i,cfg['id'],dict(collections.Counter(r['oracle']['status'] for r in rows)),flush=True)
            meta=dict(runs=len(rows),cases=len(cfgs),browser=browser.version,repeats=1 if args.smoke else args.repeats,
                      wall_seconds=time.perf_counter()-start,counts=dict(collections.Counter(r['oracle']['status'] for r in rows)),
                      receipt_count=sum(len(r['server_records']) for r in rows),scope='two text fields; authored workflows; production bundles; offline browser prerender; actual loopback requests')
            output.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2))
            output.with_suffix('.rendered.json').write_text(json.dumps(rendered,indent=2))
            print(json.dumps(meta),flush=True);browser.close()
    finally:proc.terminate();proc.wait(timeout=10)
    if any(r['oracle']['status']=='inconclusive' for r in rows):raise RuntimeError('Incomplete browser evidence, inspect raw rows')

if __name__=='__main__':main()
