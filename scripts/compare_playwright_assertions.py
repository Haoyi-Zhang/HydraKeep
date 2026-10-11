#!/usr/bin/env python3
"""Same-execution explicit Playwright assertions versus transaction monitoring.

The comparison supplies BOTH systems the same immutable-snapshot contract and
receiver bodies. Three two-text workflows deliberately avoid reset/removal so
that the baseline is a short ordinary regression, not a second general monitor.
These are additional browser runs, not reinterpretations of the main matrix.
"""
from __future__ import annotations
import collections
import itertools
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from evidence_admission import admit_browser_trace, typed_equal
from transaction_oracle import interpret_transactions, diagnosis
from transaction_spec import specify
CASES = json.loads((ROOT / 'fixtures/transactions/cases.json').read_text())
CONTRACTS = json.loads((ROOT / 'fixtures/transactions/contracts.json').read_text())
ENDPOINT = 'http://127.0.0.1:8774'


def validate(rows):
    selected = [c for c in CASES if c['pattern'] in ('snapshot', 'late-read', 'stale-closure')]
    expected = set(itertools.product([c['id'] for c in selected], ('pre','post'),
                                    (('t1','t2'),('t2','t1')), range(2)))
    cells = [(r['case'],r['gap'],tuple(r['dispatch_order']),r['rep']) for r in rows]
    if len(cells) != len(set(cells)) or set(cells) != expected:
        raise ValueError('Missing or duplicate assertion-comparison cell')
    for row in rows:
        contract = CONTRACTS[row['case']]
        admit_browser_trace(row['trace'], contract)
        if (row.get('page_errors') or interpret_transactions(row['trace'],contract) != row['oracle']
                or specify(row['trace'],contract) != row['reference']):
            raise ValueError('Comparison execution or interpreter mismatch')
        receipts = [e for e in row['trace'] if e['type']=='receipt']
        dispatches = [e for e in row['trace'] if e['type']=='dispatch']
        if len(row['server_records']) != 2: raise ValueError('Missing comparison receiver')
        for receipt, dispatch, record in zip(receipts,dispatches,row['server_records'],strict=True):
            if (receipt['transaction'] != dispatch['transaction'] or
                    receipt['transaction'] != record['transaction'] or
                    record.get('run') != row['run']+':'+receipt['transaction'] or
                    not typed_equal(receipt['payload'],json.loads(record['body'])) or
                    not typed_equal(receipt['payload'],json.loads(dispatch['body']))):
                raise ValueError('Comparison receipt chain mismatch')
    return len(rows)


def execute(browser, cfg, html, gap, order, rep, run):
    from playwright.sync_api import expect
    from run_transactions import init, load, edit
    page = browser.new_page()
    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
    row = dict(case=cfg['id'], framework=cfg['framework'], pattern=cfg['pattern'],
               gap=gap, dispatch_order=list(order), rep=rep, run=run,
               evidence_class='same-execution-playwright-assertion-comparison', server_records=[])
    baseline_failures = []
    expected = {}; frozen = {}

    def display(stage):
        for field, wanted in expected.items():
            try:
                expect(page.locator('[data-hk-field="' + field + '"]')).to_have_value(wanted, timeout=100)
            except AssertionError:
                baseline_failures.append(dict(kind='display-loss', field=field, stage=stage))

    try:
        init(page, cfg, run, html); page.evaluate('tx.emit("checkpoint")')
        if gap == 'post':
            load(page, cfg); page.evaluate('txApp.mount(CFG)')
            page.evaluate('tx.phase="hydrated";tx.emit("checkpoint")')
        edit(page, 'a', 'toy-a1'); expected['a'] = 'toy-a1'; display('edit-a1')
        edit(page, 'b', 'toy-b1'); expected['b'] = 'toy-b1'; display('edit-b1')
        if gap == 'pre':
            load(page, cfg); page.evaluate('txApp.mount(CFG)')
            page.evaluate('tx.phase="hydrated";tx.emit("checkpoint")'); display('hydrated')
        frozen['t1'] = dict(expected); display('consume-t1')
        page.locator('#submit').click(); page.evaluate('tx.settle()')
        page.evaluate('tx.phase="after-first-consume";tx.emit("checkpoint")'); display('after-t1')
        edit(page, 'a', 'toy-a2'); expected['a'] = 'toy-a2'; display('edit-a2')
        frozen['t2'] = dict(expected); display('consume-t2')
        page.locator('#submit').click(); page.evaluate('tx.settle()')
        page.evaluate('tx.phase="after-second-consume";tx.emit("checkpoint")'); display('after-t2')
        for tx in order:
            page.evaluate('(id)=>tx.phase="receipt-"+id', tx)
            consumer = page.evaluate('(id)=>tx.release(id)', tx)
            records = json.load(urllib.request.urlopen(ENDPOINT + '/records?run=' + run + ':' + tx, timeout=5))
            if len(records) != 1: raise ValueError('Nonunique receiver record')
            record = records[0]; record.update(transaction=tx, consumer=consumer)
            row['server_records'].append(record); payload = json.loads(record['body'])
            # An ordinary assertion supplied with the SAME frozen transaction value.
            try:
                assert typed_equal(payload, frozen[tx])
            except AssertionError:
                baseline_failures.append(dict(kind='consumer-loss', transaction=tx,
                                              expected=frozen[tx], actual=payload))
            page.evaluate('(data)=>tx.emit("receipt",data)',
                          dict(transaction=tx, consumer=consumer, channel='application', payload=payload))
            display('receipt-' + tx)
        row['trace'] = page.evaluate('tx.trace')
        admit_browser_trace(row['trace'], CONTRACTS[cfg['id']])
        row['oracle'] = interpret_transactions(row['trace'], CONTRACTS[cfg['id']])
        row['reference'] = specify(row['trace'], CONTRACTS[cfg['id']])
        if diagnosis(row['oracle']) != diagnosis(row['reference']) or errors:
            raise ValueError('Browser error or specification disagreement')
        row['assertions'] = dict(status='violation' if baseline_failures else 'clean',
                                 failures=baseline_failures)
        row['page_errors'] = errors
    finally:
        page.close()
    return row


def main():
    from playwright.sync_api import sync_playwright
    from run_transactions import prerender
    selected = [c for c in CASES if c['pattern'] in ('snapshot', 'late-read', 'stale-closure')]
    out = ROOT / 'results/assertion-comparison'; out.mkdir(exist_ok=True)
    server = subprocess.Popen(['node', 'src/server.mjs'], cwd=ROOT,
                              env={**os.environ, 'PORT':'8774'}, stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if server.poll() is not None: raise RuntimeError('Owned loopback receiver exited')
            try:
                urllib.request.urlopen(ENDPOINT + '/health', timeout=.2).close(); break
            except OSError: time.sleep(.1)
        else: raise RuntimeError('Owned loopback receiver unavailable')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ['CHROMIUM_PATH'], headless=True)
            rendered = {c['id']:prerender(browser,c) for c in selected}
            rows = []
            with (out / 'runs.jsonl').open('w') as stream:
                for index, (cfg,gap,order,rep) in enumerate(itertools.product(
                        selected, ('pre','post'), (('t1','t2'),('t2','t1')), range(2)), 1):
                    row = execute(browser,cfg,rendered[cfg['id']],gap,order,rep,'assertion-'+str(index))
                    rows.append(row); stream.write(json.dumps(row)+'\n'); stream.flush()
            validate(rows)
            disagreements = sum(row['assertions']['status'] != row['oracle']['status'] for row in rows)
            summary = dict(browser=browser.version, runs=len(rows), receipts=2*len(rows),
                           cells=len(rows)//2, repetitions=2, configurations=len(selected),
                           patterns=3, status_counts=dict(collections.Counter(r['oracle']['status'] for r in rows)),
                           assertion_monitor_status_disagreements=disagreements,
                           scope='same executions; explicit text-value and immutable receiver-snapshot assertions; no reset, removal or throughput comparison')
            (out / 'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
            browser.close()
            if disagreements or len(rows) != 48: raise ValueError('Comparison incomplete or disagreement')
            print(json.dumps(summary,indent=2))
    finally:
        server.terminate(); server.wait(timeout=10)


if __name__ == '__main__': main()
