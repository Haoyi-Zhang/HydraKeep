#!/usr/bin/env python3
"""Recompute all published numbers from actual browser JSONL; no fabricated data."""
from __future__ import annotations
import json,csv,pathlib,sys,statistics,random,collections
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from oracle import interpret
from explorer import grid,quotient,Schedule,phase_class,ordered
C=json.loads((ROOT/'fixtures/contracts.json').read_text());CASES=json.loads((ROOT/'fixtures/cases.json').read_text());CM={c['id']:c for c in CASES}
def load(name):return [json.loads(l) for l in (ROOT/'results'/name).read_text().splitlines()]
def sig(r):
    o=r['oracle'];return (o['status'],tuple(sorted({(f['kind'],f['phase']) for f in o['failures']})),o['accepted_edits'],o['blocked_edits'])
def csvwrite(name,rows):
    p=ROOT/'results'/name
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    rows=load('grid.jsonl');base=[r for r in rows if r['rep']==0];lookup={(r['case'],r['horizon'],r['gap']):r for r in base}
    assert len(base)==540 and len(lookup)==540,'The complete 30 x 18 reference is required.'
    assert len(rows)==1080,'Two complete repetitions are required.'
    expected={(c['id'],s.horizon,s.gap,rep) for c in CASES for s in grid() for rep in [0,1]}
    assert {(r['case'],r['horizon'],r['gap'],r['rep']) for r in rows}==expected, 'Missing, duplicated or unexpected reference schedule.'
    replay_mismatch=[(r['case'],r['horizon'],r['gap'],r['rep']) for r in rows if interpret(r['trace'],C[r['case']])!=r['oracle']]
    assert not replay_mismatch, f'Oracle recomputation disagreed: {replay_mismatch[:5]}'
    rep_disagreements=[(r['case'],r['horizon'],r['gap']) for r in rows if r['rep']>0 and sig(r)!=sig(lookup[(r['case'],r['horizon'],r['gap'])])]
    equivalence_disagreements=[]
    for case in CASES:
        groups={}
        for s in grid():
            r=lookup[(case['id'],s.horizon,s.gap)];key=phase_class(s)
            if key in groups and sig(r)!=sig(groups[key]):equivalence_disagreements.append((case['id'],s.horizon,s.gap))
            else:groups[key]=r
    percase=[];bad=set();clean=set()
    for case in CASES:
        cr=[r for r in base if r['case']==case['id']];counts=collections.Counter(r['oracle']['status'] for r in cr)
        failures={f['kind'] for r in cr for f in r['oracle']['failures']}
        if counts['violation']:bad.add(case['id'])
        else:clean.add(case['id'])
        percase.append(dict(case=case['id'],framework=case['framework'],split=case['split'],kind=case['kind'],design=case['design'],violating=counts['violation'],clean=counts['clean'],no_edit=counts['no-edit'],inconclusive=counts['inconclusive'],failure_kinds=';'.join(sorted(failures))))
    csvwrite('configurations.csv',percase)
    qset={(s.horizon,s.gap) for s in quotient()}
    selectors={
      'Post-load E2E':lambda r:r['horizon']=='T' and r['gap']==7,
      'Fixed release, contract oracle':lambda r:r['horizon']=='H' and r['gap']==0,
      'Phase grid':lambda r:True,
      'Phase quotient':lambda r:(r['horizon'],r['gap']) in qset,
    }
    baseline=[]
    for name,sel in selectors.items():
        selected=[r for r in base if sel(r)];det={r['case'] for r in selected if r['oracle']['status']=='violation'}
        baseline.append(dict(method=name,runs=len(selected),detected_configurations=len(det),reference_violating_configurations=len(bad),extra_vs_reference=len(det-bad),sum_measured_run_seconds=sum(r['duration_ms'] for r in selected)/1000,selected_case_ids=';'.join(sorted(det))))
    # Diagnostic sensors are replayed on the entire common reference, not claimed tool executions.
    warn=lambda r:bool(r['console'] or any(e['type']=='recoverable-error' for e in r['trace']))
    dom=lambda r:any(f['kind']=='dom-loss' for f in r['oracle']['failures'])
    for name,sensor in [('Production warning sensor',warn),('DOM-only contract sensor',dom)]:
        det={r['case'] for r in base if sensor(r)}
        baseline.append(dict(method=name,runs=len(base),detected_configurations=len(det),reference_violating_configurations=len(bad),extra_vs_reference=len(det-bad),sum_measured_run_seconds=sum(r['duration_ms'] for r in base)/1000,selected_case_ids=';'.join(sorted(det))))
    csvwrite('baselines.csv',baseline)
    ab=[]
    for abl in ['drop-identity','strict-node','attribute-only']:
        new={id(r):interpret(r['trace'],C[r['case']],ablation=abl) for r in base}
        missed=[r for r in base if r['oracle']['status']=='violation' and new[id(r)]['status']!='violation']
        extra=[r for r in base if r['oracle']['status'] in ['clean','no-edit'] and new[id(r)]['status']=='violation']
        ab.append(dict(ablation=abl,missed_reference_runs=len(missed),extra_flags_on_reference_clean_runs=len(extra),missed_case_ids=';'.join(sorted({r['case'] for r in missed})),extra_case_ids=';'.join(sorted({r['case'] for r in extra}))))
    csvwrite('ablations.csv',ab)
    # Explicit manual dependency hints: no automated source analyzer is claimed.
    hints={c['id']:('keyed' if c['design'].startswith('replace') else 'native' if c['design'] in ['native','uncontrolled'] else 'state-binding') for c in CASES}
    (ROOT/'fixtures/hints.json').write_text(json.dumps({'origin':'manual dependency-role annotation; priorities only, never the oracle','hints':hints},indent=2))
    budget=[]
    for b in range(1,10):
        for name,with_hint in [('phase-order',False),('manual-hint-order',True)]:
            selections=[lookup[(c['id'],s.horizon,s.gap)] for c in CASES for s in ordered(quotient(),hints[c['id']] if with_hint else None)[:b]]
            budget.append(dict(order=name,budget_per_configuration=b,runs=len(selections),detected_configurations=len({r['case'] for r in selections if r['oracle']['status']=='violation'}),sum_measured_run_seconds=sum(r['duration_ms'] for r in selections)/1000))
    csvwrite('budget.csv',budget)
    stateonly=[r for r in base if any(f['kind']=='state-only-loss' for f in r['oracle']['failures'])]
    invisible=[r for r in base if r['oracle']['status']=='violation' and not dom(r)]
    phase_counts=collections.Counter()
    for r in base:
        if r['oracle']['failures']:phase_counts[r['oracle']['failures'][0]['phase']]+=1
    # Descriptive cluster bootstrap: 13 cross-framework pairs + four singleton holdouts.
    # Not a confidence statement about a Web-site population.
    clusters=[[f'R{i:02}',f'V{i:02}'] for i in range(1,14)]+[[x] for x in ['R14','R15','V14','V15']]
    fixed=set(next(x for x in baseline if x['method']=='Fixed release, contract oracle')['selected_case_ids'].split(';'))
    differences=[sum((cid in bad)-(cid in fixed) for cid in group)/len(group) for group in clusters]
    rng=random.Random(4301);boots=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(5000))
    out=dict(configurations=30,reference_schedules=540,total_grid_runs=len(rows),counts_reference=dict(collections.Counter(r['oracle']['status'] for r in base)),violating_configurations=len(bad),violation_ids=sorted(bad),nonviolating_configurations=len(clean),nonviolating_ids=sorted(clean),repeat_signature_disagreements=len(rep_disagreements),equivalence_signature_disagreements=len(equivalence_disagreements),equivalence_classes=270,comparison_edges=270,state_only_runs=len(stateonly),state_only_case_ids=sorted({r['case'] for r in stateonly}),dom_invisible_violation_runs=len(invisible),dom_invisible_case_ids=sorted({r['case'] for r in invisible}),production_warning_runs=sum(warn(r) for r in base),first_failure_phase=dict(phase_counts),baseline=baseline,ablations=ab,budget=budget,holdout_counts={s:len({r['case'] for r in base if r['split']==s and r['oracle']['status']=='violation'}) for s in ['development','holdout']},cluster_bootstrap={'units':17,'replicates':5000,'seed':4301,'estimand':'equal-cluster mean detection difference (grid minus fixed release); descriptive resampling sensitivity, not Web-population coverage','observed':statistics.mean(differences),'percentile_2_5':boots[125],'percentile_97_5':boots[4874]})
    qpath=ROOT/'results/quotient.jsonl'
    if qpath.exists():
        qr=load('quotient.jsonl');assert len(qr)==270
        assert {(r['case'],r['horizon'],r['gap']) for r in qr}=={(c['id'],s.horizon,s.gap) for c in CASES for s in quotient()}, 'Incomplete quotient schedule set.'
        assert all(interpret(r['trace'],C[r['case']])==r['oracle'] for r in qr), 'Quotient oracle recomputation disagreed.'
        disagreements=[(r['case'],r['horizon'],r['gap']) for r in qr if sig(r)!=sig(lookup[(r['case'],r['horizon'],r['gap'])])]
        out['separate_quotient']={'runs':len(qr),'reference_signature_disagreements':len(disagreements),'sum_run_seconds':sum(r['duration_ms'] for r in qr)/1000,'meta':json.loads((ROOT/'results/quotient.meta.json').read_text())}
    out['grid_meta']=json.loads((ROOT/'results/grid.meta.json').read_text())
    (ROOT/'results/summary.json').write_text(json.dumps(out,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k not in ['budget','baseline']},indent=2))
if __name__=='__main__':main()
