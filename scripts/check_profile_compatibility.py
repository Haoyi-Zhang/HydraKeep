#!/usr/bin/env python3
"""Monitor compatibility on retained data; NOT additional browser executions.

The old implicit receipt rule is lowered to a virtual consume immediately before
receipt. This virtual event is an interpretation equivalence, not claimed browser
instrumentation. Existing explicit terminal consumes are retained and identified.
"""
from __future__ import annotations
import copy, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form, signature
from transaction_oracle import interpret_transactions
FILES=['phase-grid/multi-grid.jsonl','phase-grid/multi-quotient.jsonl',
       'native-integration/matrix-chromium.jsonl','native-integration/matrix-quotient-chromium.jsonl','native-integration/versions-chromium.jsonl']
CONTRACTS=json.loads((ROOT/'fixtures/multi/contracts.json').read_text())
KIND={'display-loss':'dom-loss','consumer-only-loss':'state-only-loss'}


def lower(trace,fields):
    explicit=any(e['type']=='consume' for e in trace)
    result=[]
    for original in trace:
        e=copy.deepcopy(original)
        if e['type']=='receipt' and not explicit:
            result.append({**e,'type':'consume','transaction':'legacy-one','consumer':'terminal'})
        if e['type'] in ['consume','receipt']:
            e.update(transaction='legacy-one',consumer='terminal')
        result.append(e)
    return result


def compare(trace,contract):
    legacy=interpret_form(trace,contract)
    c=dict(fields=contract,consumers={'terminal':dict(fields=list(contract),release_display=list(contract),channel='application')})
    current=interpret_transactions(lower(trace,contract),c)
    fs=tuple(sorted({(f['field'],KIND.get(f['kind'],f['kind']),f['phase'],f['epoch']) for f in current['failures']}))
    sig=(current['status'],fs,current['accepted_edits'],current['blocked_edits'])
    if sig!=signature(legacy):raise ValueError({'legacy':legacy,'transaction':current})
    return current


def main():
    studies=[];total=0
    for name in FILES:
        rows=[json.loads(l) for l in (ROOT/'results'/name).read_text().splitlines()]
        for row in rows:compare(row['trace'],CONTRACTS[row['case']])
        studies.append(dict(file=name,traces=len(rows),diagnostic_disagreements=0));total+=len(rows)
    result=dict(retained_trace_reinterpretations=total,diagnostic_disagreements=0,studies=studies,
                new_browser_runs=0,lowering='implicit legacy receipts use a virtual receipt-local terminal consume; no event is claimed to have been recorded')
    (ROOT/'results/transactions/profile-compatibility.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
