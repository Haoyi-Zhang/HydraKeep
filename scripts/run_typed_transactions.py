#!/usr/bin/env python3
"""Heterogeneous two-consumption study with typed controls and HTTP receipts."""
from __future__ import annotations
import argparse, collections, itertools, json, os, pathlib, shutil, signal, socket, subprocess, sys, tempfile, time, urllib.request
from typing import Any
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from transaction_oracle import interpret_transactions
from transaction_spec import specify
CASES=json.loads((ROOT/'fixtures/typed-transactions/cases.json').read_text())
CONTRACTS=json.loads((ROOT/'fixtures/typed-transactions/contracts.json').read_text())
ENDPOINT='http://127.0.0.1:8775'


def launch_external_browser(playwright, executable):
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    profile=tempfile.mkdtemp(prefix='hydrakeep-chromium-')
    command=[executable,'--headless=new','--no-sandbox','--disable-gpu',
             '--remote-debugging-address=127.0.0.1',f'--remote-debugging-port={port}',
             f'--user-data-dir={profile}','about:blank']
    process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             start_new_session=True)
    endpoint=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            if process.poll() is not None:raise RuntimeError('External Chromium exited during startup')
            try:
                with urllib.request.urlopen(endpoint+'/json/version',timeout=.2) as response:
                    if response.status==200:break
            except OSError:time.sleep(.05)
        else:raise RuntimeError('External Chromium debugging endpoint unavailable')
        browser=playwright.chromium.connect_over_cdp(endpoint)
        return browser,process,profile
    except Exception:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        shutil.rmtree(profile,ignore_errors=True)
        raise


def stop_external_browser(process,profile):
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
    shutil.rmtree(profile,ignore_errors=True)



def init(page,cfg,run,markup=''):
    page.set_default_timeout(5000)
    page.set_content('<!doctype html><html><head><meta charset="utf-8"><style>'
                     'body{padding:20px}label,input,select,button{font-size:18px;margin:8px}'
                     '</style></head><body><div id="root">'+markup+'</div></body></html>')
    page.evaluate('(o)=>Object.assign(window,o)',dict(CFG=cfg,RUN=run,ENDPOINT=ENDPOINT))
    page.add_script_tag(content=(ROOT/'src/typed-transaction-observer.js').read_text())


def load(page,cfg):
    version='19.1.1' if cfg['framework']=='react' else '3.5.13'
    page.add_script_tag(content=(ROOT/f'vendor/{cfg["framework"]}-{version}.production.js').read_text())
    page.add_script_tag(content=(ROOT/f'src/typed-transaction-{cfg["framework"]}.js').read_text())


def prerender(browser,cfg):
    page=browser.new_page()
    try:
        init(page,cfg,'prerender');load(page,cfg);page.evaluate('txApp.mount(CFG,true)')
        page.evaluate('''()=>{for(const el of document.querySelectorAll('[data-hk-field]')) {
          if (el instanceof HTMLInputElement && el.type === 'checkbox') {
            if (el.checked) el.setAttribute('checked',''); else el.removeAttribute('checked');
          } else if (el instanceof HTMLSelectElement) {
            for (const option of el.options) {
              if (option.selected) option.setAttribute('selected',''); else option.removeAttribute('selected');
            }
          } else el.setAttribute('value',el.value);
        }}''')
        return page.locator('#root').inner_html()
    finally:
        # The enclosing isolated Chromium process is killed after this configuration.
        # Closing pages after trusted native select input can hang in some headless builds.
        pass


def edit(page,fid,value:Any):
    loc=page.locator('[data-hk-field="'+fid+'"]')
    if loc.count()!=1:raise RuntimeError('Non-unique edit target: '+fid)
    if not loc.is_enabled() or loc.get_attribute('readonly') is not None:
        page.evaluate('(field)=>tx.emit("edit-blocked",{field})',fid);return
    kind=page.evaluate('(field)=>tx.fields().find(item=>item.id===field)?.control',fid)
    if kind=='checkbox':
        (loc.check if value else loc.uncheck)()
    elif kind == 'select-one':
        options=loc.locator('option').evaluate_all('(nodes)=>nodes.map(node=>node.value)')
        if value not in options:raise RuntimeError('Unknown select option: '+str(value))
        # All profile options have distinct first letters. A real key press changes
        # the native selection without opening a browser-owned popup.
        loc.focus();page.keyboard.press(str(value)[0])
        if loc.input_value()!=str(value):raise RuntimeError('Native select did not reach requested value: '+str(value))
    elif kind == 'select-multiple':
        raise RuntimeError('Multiple select is outside this profile')
    else:
        loc.click();loc.press('ControlOrMeta+A');loc.press_sequentially(str(value))
    page.evaluate('''([field,requested])=>tx.emit("edit",{
      field,requested,trusted:tx.last[field]?.trusted===true})''',[fid,value])


def execute(browser,cfg,html,gap,order,rep,run):
    started=time.perf_counter();page=browser.new_page();errors=[];warnings=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('console',lambda message:warnings.append(message.text) if message.type in ['warning','error'] else None)
    row=dict(case=cfg['id'],framework=cfg['framework'],pattern=cfg['pattern'],gap=gap,
             dispatch_order=list(order),rep=rep,run=run,
             evidence_class='offline-browser-prerender-heterogeneous-controls-loopback-http',
             server_records=[])
    try:
        init(page,cfg,run,html);page.evaluate('tx.emit("checkpoint")')
        if gap=='post':
            load(page,cfg);page.evaluate('txApp.mount(CFG)');page.evaluate('tx.phase="hydrated";tx.emit("checkpoint")')
        edit(page,'name','toy-name1');edit(page,'agree',True);edit(page,'tier','pro')
        if gap=='pre':
            load(page,cfg);page.evaluate('txApp.mount(CFG)');page.evaluate('tx.phase="hydrated";tx.emit("checkpoint")')
        page.locator('#submit').click();page.evaluate('tx.settle()')
        page.evaluate('tx.phase="after-first-consume";tx.emit("checkpoint")')
        if cfg['pattern'] in ['epoch-reset','stale-after-reset']:
            page.locator('#reset-tier').click();page.evaluate('tx.settle()');page.evaluate('tx.emit("checkpoint")')
        if cfg['pattern']=='replacement':
            before=page.evaluate('tx.fields().find(field=>field.id==="name").node')
            page.locator('#replace-name').click();page.evaluate('tx.settle()');page.evaluate('tx.emit("checkpoint")')
            after=page.evaluate('tx.fields().find(field=>field.id==="name").node')
            if before==after:raise RuntimeError('Replacement control did not replace the physical node')
        if cfg['pattern']=='scoped-submit':edit(page,'agree',False)
        elif cfg['pattern']=='overbroad-clear':edit(page,'agree',True)
        elif cfg['pattern'] in ['epoch-reset','stale-after-reset']:edit(page,'tier','enterprise')
        elif cfg['pattern']=='replacement':edit(page,'agree',False)
        else:edit(page,'name','toy-name2')
        page.locator('#submit').click();page.evaluate('tx.settle()')
        page.evaluate('tx.phase="after-second-consume";tx.emit("checkpoint")')
        for tid in order:
            page.evaluate('(id)=>tx.phase="receipt-"+id',tid)
            consumer=page.evaluate('''(id)=>Promise.race([tx.release(id),
              new Promise((_,reject)=>setTimeout(()=>reject(new Error('release timeout')),8000))])''',tid)
            records=json.load(urllib.request.urlopen(ENDPOINT+'/records?run='+run+':'+tid,timeout=5))
            if len(records)!=1:raise RuntimeError('Nonunique server receipt: '+tid)
            record=records[0];record.update(transaction=tid,consumer=consumer)
            row['server_records'].append(record)
            payload=json.loads(record['body'])
            page.evaluate('(data)=>tx.emit("receipt",data)',dict(transaction=tid,consumer=consumer,
                                                                  channel='application',payload=payload))
        row['trace']=page.evaluate('tx.trace')
        row['oracle']=interpret_transactions(row['trace'],CONTRACTS[cfg['id']])
        row['reference']=specify(row['trace'],CONTRACTS[cfg['id']])
        row['page_errors']=errors;row['console']=warnings
        if errors:raise RuntimeError('Browser errors: '+repr(errors))
    except Exception as exc:
        row['error']=str(exc)
        row.setdefault('trace',page.evaluate('window.tx?.trace || []'))
        row['oracle']=dict(status='inconclusive',unknown=[str(exc)],failures=[])
    finally:
        # Process-isolated teardown handles this page; see prerender().
        pass
    row['duration_ms']=(time.perf_counter()-started)*1000
    return row


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--repeats',type=int,default=2);parser.add_argument('--output',default=None)
    parser.add_argument('--case',action='append',default=[],help='Run only this configuration ID; repeatable')
    parser.add_argument('--rep-offset',type=int,default=0,help='Starting repetition label for sharded runs')
    args=parser.parse_args()
    if args.repeats<1:raise SystemExit('repeats must be positive')
    default='results/typed-transactions/smoke.jsonl' if args.smoke else 'results/typed-transactions/runs.jsonl'
    output=ROOT/(args.output or default);output.parent.mkdir(parents=True,exist_ok=True)
    patterns=['typed-snapshot','checkbox-coercion','scoped-submit','replacement']
    cfgs=CASES if not args.smoke else [case for case in CASES if case['pattern'] in patterns]
    if args.case:
        requested=set(args.case);cfgs=[case for case in cfgs if case['id'] in requested]
        missing=requested-{case['id'] for case in cfgs}
        if missing:raise SystemExit('Unknown case IDs: '+', '.join(sorted(missing)))
    proc=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,env={**os.environ,'PORT':'8775'},stdout=subprocess.DEVNULL)
    rows=[];started_at=time.time_ns()
    try:
        for _ in range(50):
            if proc.poll() is not None:raise RuntimeError('Local receiver exited; port 8775 may be unavailable')
            try:
                with urllib.request.urlopen(ENDPOINT+'/health',timeout=.2) as response:
                    if response.read()==b'ok':break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Local receiver unavailable')
        with sync_playwright() as playwright:
            executable=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium')
            repetitions=1 if args.smoke else args.repeats
            browser_version=None;rendered_all={}
            with output.open('w') as stream:
                index=0
                for rep_index in range(repetitions):
                    rep=args.rep_offset+rep_index
                    gaps=['pre'] if args.smoke else ['pre','post']
                    orders=[('t2','t1')] if args.smoke else [('t1','t2'),('t2','t1')]
                    # Native select interaction can leave browser-owned popup state alive in
                    # long sessions. Small independent chunks keep repetitions isolated.
                    chunk_size=1
                    for start in range(0,len(cfgs),chunk_size):
                        chunk=cfgs[start:start+chunk_size]
                        browser,browser_process,browser_profile=launch_external_browser(playwright,executable)
                        try:
                            browser_version=browser.version
                            rendered={case['id']:prerender(browser,case) for case in chunk};rendered_all.update(rendered)
                            for cfg,gap,order in itertools.product(chunk,gaps,orders):
                                index+=1
                                run_id=f"typed-{cfg['id']}-r{rep}-{gap}-{''.join(order)}"
                                row=execute(browser,cfg,rendered[cfg['id']],gap,order,rep,run_id)
                                rows.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
                                if args.smoke or index%8==0:
                                    print(index,cfg['id'],dict(collections.Counter(r['oracle']['status'] for r in rows)),flush=True)
                        finally:
                            stop_external_browser(browser_process,browser_profile)
            meta=dict(runs=len(rows),cases=len(cfgs),browser=browser_version,repeats=repetitions,
                      wall_seconds=(time.time_ns()-started_at)/1_000_000_000,
                      counts=dict(collections.Counter(row['oracle']['status'] for row in rows)),
                      receipt_count=sum(len(row['server_records']) for row in rows),
                      scope='text, checkbox, single-select; paired React/Vue authored workflows; actual loopback receipts')
            output.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2)+'\n')
            output.with_suffix('.rendered.json').write_text(json.dumps(rendered_all,indent=2)+'\n')
            print(json.dumps(meta),flush=True)
    finally:
        proc.terminate();proc.wait(timeout=10)
    if any(row['oracle']['status']=='inconclusive' for row in rows):
        raise RuntimeError('Incomplete browser evidence, inspect raw rows')

if __name__=='__main__':main()
