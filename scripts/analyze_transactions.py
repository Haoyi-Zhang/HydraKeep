#!/usr/bin/env python3
"""Recompute transaction results and reject incomplete/mismatched evidence."""
from __future__ import annotations
import collections, copy, csv, itertools, json, math, pathlib, statistics, sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from transaction_oracle import interpret_transactions, diagnosis
from transaction_spec import specify
from test_transactions import generated_traces
OUT=ROOT/'results/transactions'; PAPER=ROOT.parent/'paper/generated/transactions'
CASES=json.loads((ROOT/'fixtures/transactions/cases.json').read_text())
CONTRACTS=json.loads((ROOT/'fixtures/transactions/contracts.json').read_text())


def require(ok,message):
    if not ok:raise ValueError(message)


def typed_json_equal(a, b):
    """JSON equality without Python's bool/int coercion; object order is immaterial."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_json_equal(x, y) for x, y in zip(a, b))
    return a == b


def validate(rows):
    expected=set(itertools.product([c['id'] for c in CASES],['pre','post'],[('t1','t2'),('t2','t1')],range(2)))
    keys=[(r['case'],r['gap'],tuple(r['dispatch_order']),r['rep']) for r in rows]
    require(len(keys)==len(set(keys)),'Duplicate experiment cell')
    require(set(keys)==expected,'Missing/unexpected experiment cell')
    actual={};seen_runs=set();declared={c["id"]:c for c in CASES}
    for row in rows:
        require(row['run'] not in seen_runs,'Duplicate run identity');seen_runs.add(row['run'])
        require(not row.get('error') and not row.get('page_errors'),'Browser execution error')
        case=declared[row['case']]
        require(row['framework']==case['framework'] and row['pattern']==case['pattern'],
                'Case metadata differs from the declared design')
        require(row['evidence_class']=='offline-browser-prerender-real-hydration-loopback-http',
                'Incorrect evidence classification')
        require(type(row['duration_ms']) in (int, float) and math.isfinite(row['duration_ms'])
                and row['duration_ms'] >= 0, 'Invalid measured duration')
        contract=CONTRACTS[row['case']];trace=row['trace']
        result=interpret_transactions(trace,contract);reference=specify(trace,contract)
        require(result==row['oracle'],'Stored monitor result differs')
        require(reference==row['reference'],'Stored specification result differs')
        require(diagnosis(result)==diagnosis(reference),'Specification/implementation disagreement')
        require(result['status']!='inconclusive','Incomplete trace')
        require(result['accepted_edits']==3 and result['consumptions']==2 and result['receipts']==2,'Unexpected evidence counts')
        receipts=[e for e in trace if e['type']=='receipt']
        dispatches=[e for e in trace if e['type']=='dispatch']
        require([e['transaction'] for e in receipts]==row['dispatch_order'],'Receipt ordering differs')
        require(len(row['server_records'])==2 and len(dispatches)==2,'Missing/duplicate HTTP evidence')
        for observed,record,dispatch in zip(receipts,row['server_records'],dispatches):
            require(observed['transaction']==record['transaction']==dispatch['transaction'],'Transaction correspondence differs')
            require(observed['consumer']==record['consumer']==dispatch['consumer'],'Consumer correspondence differs')
            require(record['contentType'].split(';')[0]=='application/json','Unexpected receiver content type')
            require(typed_json_equal(json.loads(record['body']), observed['payload']) and
                    typed_json_equal(observed['payload'], json.loads(dispatch['body'])), 'Payload chain differs')
        key=(row['case'],row['gap'],tuple(row['dispatch_order']))
        if key in actual:require(actual[key]==diagnosis(result),'Repeat diagnostic instability')
        else:actual[key]=diagnosis(result)
    # Paired implementations are not independent applications.
    for row in rows:
        if row['framework']=='react':
            other='TV'+row['case'][2:]
            require(actual[(row['case'],row['gap'],tuple(row['dispatch_order']))]==actual[(other,row['gap'],tuple(row['dispatch_order']))],
                    'Paired React/Vue diagnostic disagreement')
    return actual


def main():
    rows=[json.loads(l) for l in (OUT/'transactions.jsonl').read_text().splitlines()]
    validate(rows)
    model=collections.Counter();mutants=collections.Counter();model_count=0
    for c,t in generated_traces():
        monitor=interpret_transactions(t,c);reference=specify(t,c)
        require(diagnosis(monitor)==diagnosis(reference),'Model differential failure')
        model[monitor['status']]+=1;model_count+=1
        for variant in ['global-release','latest-at-receipt','dom-only']:
            if diagnosis(interpret_transactions(t,c,ablation=variant))!=diagnosis(monitor):mutants[variant]+=1
    summaries=[]
    for pattern in dict.fromkeys(c['pattern'] for c in CASES):
        subset=[r for r in rows if r['pattern']==pattern]
        counts=collections.Counter(r['oracle']['status'] for r in subset)
        summaries.append(dict(workflow=pattern,runs=len(subset),clean=counts['clean'],violation=counts['violation'],
              consumer_only=sum(any(f['kind']=='consumer-only-loss' for f in r['oracle']['failures']) and
                  not any(f['kind']=='display-loss' for f in r['oracle']['failures']) for r in subset),
              median_ms=round(statistics.median(r['duration_ms'] for r in subset),3)))
    ablations=[]
    for variant in ['global-release','latest-at-receipt','dom-only']:
        false_negative=false_positive=inconclusive=0
        for r in rows:
            value=interpret_transactions(r['trace'],CONTRACTS[r['case']],ablation=variant)
            false_negative+=r['oracle']['status']=='violation' and value['status']=='clean'
            false_positive+=r['oracle']['status']=='clean' and value['status']=='violation'
            inconclusive+=value['status']=='inconclusive'
        ablations.append(dict(variant=variant,missed_violating_traces=false_negative,false_alarms_on_clean_traces=false_positive,inconclusive=inconclusive))
    PAPER.mkdir(parents=True,exist_ok=True)
    for filename,data in [('workflows.csv',summaries),('ablations.csv',ablations)]:
        for directory in [OUT,PAPER]:
            with (directory/filename).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    status=collections.Counter(r['oracle']['status'] for r in rows)
    report=dict(primary_browser_runs=len(rows),primary_http_receipts=2*len(rows),
                independent_authored_workflow_designs=len(summaries),paired_framework_configurations=len(CASES),
                unique_schedule_cells=64,repeated_cell_checks=64,repeat_diagnostic_disagreements=0,
                prefix_specification_disagreements=0,browser_counts=dict(status),
                model_trace_count=model_count,model_status_counts=dict(model),model_mutant_diagnostic_differences=dict(mutants),
                consumer_only_violating_runs=sum(r['consumer_only'] for r in summaries),
                ablations=ablations,workflows=summaries,
                scope='offline-document real-browser transaction study with loopback HTTP receivers; separate from native-SSR navigation evidence')
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    macros={'TxRuns':len(rows),'TxReceipts':2*len(rows),'TxClean':status['clean'],'TxBad':status['violation'],
            'TxStateOnly':report['consumer_only_violating_runs'],'TxModels':model_count,'CombinedRuns':7994}
    (PAPER/'numbers.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+str(v)+'}' for k,v in macros.items())+'\n')
    labels={'snapshot':'Immutable snapshot','late-read':'Deferred mutable read','stale-closure':'Stale closure','ack-clear':'Late acknowledgment reset',
            'scoped-submit':'Scoped terminal submit','overbroad-clear':'Overbroad field clearing','epoch-reset':'Permitted reset, new edit','stale-after-reset':'Stale post-reset payload'}
    lines=['\\begin{tabular}{@{}lrrr@{}}','\\toprule','Workflow & Runs & Bad & Sink only \\\\','\\midrule']
    for s in summaries:lines.append(f"{labels[s['workflow']]} & {s['runs']} & {s['violation']} & {s['consumer_only']} \\\\")
    lines+=['\\bottomrule','\\end{tabular}']
    (PAPER/'workflows.tex').write_text('\n'.join(lines)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
