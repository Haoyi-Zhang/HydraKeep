#!/usr/bin/env python3
"""Regenerate phase-grid results. Fails closed on missing grids or receipts."""
from __future__ import annotations
import json,pathlib,sys,collections,csv,statistics,random,subprocess
if not __debug__: raise RuntimeError('Evidence analysis must not run with Python -O')
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form,signature
from multi_explorer import PairSchedule,pair_grid,pair_quotient,representative,independent
from validation import validate_pair_runs
from oracle import interpret as interpret_single, same_value
from urllib.parse import parse_qs
OUT=ROOT/'results/phase-grid';GEN=ROOT.parent/'paper/generated/phase-grid';GEN.mkdir(parents=True,exist_ok=True)
def read(name):return [json.loads(l) for l in (OUT/name).read_text().splitlines()]
def key(r):return (r['case'],tuple(r['schedule'].values()))
def bad(r):return r['oracle']['status']=='violation'
def ids(rows):return sorted({r['case'] for r in rows if bad(r)})
def count(rows):return dict(collections.Counter(r['oracle']['status'] for r in rows))
def write_csv(name,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def typed_payload_equal(left, right):
 return json.dumps(left,sort_keys=True,separators=(',',':'),allow_nan=False)==json.dumps(right,sort_keys=True,separators=(',',':'),allow_nan=False)
def run():
 grid=read('multi-grid.jsonl');quot=read('multi-quotient.jsonl');ref=[r for r in grid if r['rep']==0];repeat=[r for r in grid if r['rep']==1]
 assert len(ref)==len(repeat)==608 and len(quot)==482
 assert len({key(r) for r in ref})==608
 contracts=json.loads((ROOT/'fixtures/multi/contracts.json').read_text())
 cases=json.loads((ROOT/'fixtures/multi/cases.json').read_text())
 extracted=json.loads(subprocess.check_output(['node','scripts/extract_effects.mjs','fixtures/multi/handlers.js'],cwd=ROOT))
 assert extracted['effects']==json.loads((OUT/'effects.json').read_text())['effects'], 'effect source changed: rerun and revalidate'
 proposals={c['id']:independent(extracted['effects'],c['handlers']['a'],c['handlers']['b']) for c in cases}
 validation=validate_pair_runs(grid,quot,proposals)

 for r in grid+quot:
  assert len(r.get('server_records',[]))==1 and not r.get('error') and not r.get('page_errors'),r
  assert r['server_records'][0]['contentType'].startswith('application/json')
  assert typed_payload_equal(json.loads(r['server_records'][0]['body']),next(e['payload'] for e in r['trace'] if e['type']=='receipt'))
  assert interpret_form(r['trace'],contracts[r['case']])==r['oracle']
 refmap={key(r):r for r in ref};repdiff=sum(signature(r['oracle'])!=signature(refmap[key(r)]['oracle']) for r in repeat)
 qdiff=sum(signature(r['oracle'])!=signature(refmap[key(r)]['oracle']) for r in quot)
 groups=collections.defaultdict(list)
 for r in ref:groups[(r['case'],representative(PairSchedule(**r['schedule']),r['source_independent']))].append(r)
 equivalence_bad=[g for g in groups.values() if len({signature(r['oracle']) for r in g})>1]
 state_only=[r for r in ref if bad(r) and all(f['kind']=='state-only-loss' for f in r['oracle']['failures'])]
 case_rows=[]
 for case in sorted(contracts):
  rr=[r for r in ref if r['case']==case];cc=count(rr);qq=[r for r in quot if r['case']==case]
  case_rows.append(dict(case=case,pattern=rr[0]['pattern'],framework=rr[0]['framework'],split=rr[0]['split'],reference=len(rr),representatives=len(qq),violations=cc.get('violation',0),clean=cc.get('clean',0),no_edit=cc.get('no-edit',0),state_only=sum(r in state_only for r in rr)))
 write_csv('multi-cases.csv',case_rows)
 baselines=[]
 def baseline(name,rr,separate=False,detected=None):
  detected=ids(rr) if detected is None else detected;baselines.append(dict(method=name,runs=len(rr),detected_configurations=len(detected),reference_violating_configurations=len(ids(ref)),extra_configurations=len(set(detected)-set(ids(ref))),sum_run_seconds=sum(r['duration_ms'] for r in rr)/1000,selection='separately executed' if separate else 'predeclared subset or sensor replay on reference',ids=';'.join(detected)))
 baseline('Post-hydration', [r for r in ref if r['schedule']==dict(horizon=1,a=1,b=1,order='ab')])
 baseline('Fixed pre-hydration',[r for r in ref if r['schedule']==dict(horizon=1,a=0,b=0,order='ab')])
 baseline('Phase grid',ref);baseline('Source-proposed quotient',quot,True)
 dom=[]
 for r in ref:
  q=dict(r);q['oracle']=interpret_form(r['trace'],contracts[r['case']],ablation='dom-only');dom.append(q)
 baseline('DOM-only sensor',dom)
 baseline('Production warning sensor',ref,detected=sorted({r['case'] for r in ref if r.get('console')}))
 write_csv('multi-baselines.csv',baselines)
 ab=[]
 for name in ['dom-only','global-reset','drop-identity','strict-node']:
  missed=[];extra=[]
  for r in ref:
   o=interpret_form(r['trace'],contracts[r['case']],ablation=name)
   if bad(r) and o['status']!='violation':missed.append(r)
   if r['oracle']['status'] in ['clean','no-edit'] and o['status']=='violation':extra.append(r)
  ab.append(dict(ablation=name,missed_reference_traces=len(missed),missed_cases=';'.join(sorted({r['case'] for r in missed})),extra_on_reference_clean=len(extra)))
 write_csv('multi-ablations.csv',ab)
 # Equal-case budget descriptions; no learned tuning on holdout and no fresh-baseline claim.
 budgets=[]
 for k in [1,2,4,8,16,29,38]:
  for label in ['phase-grid','source-quotient']:
   take=[]
   for c in contracts:
    rr=[r for r in (ref if label=='phase-grid' else quot) if r['case']==c];take.extend(rr[:k])
   budgets.append(dict(strategy=label,budget_per_case=k,runs=len(take),cases=len(ids(take))))
 write_csv('multi-budgets.csv',budgets)
 # Paired framework instances are NOT independent samples. Resample 8 pattern clusters.
 patterns=sorted({r['pattern'] for r in ref});fixed=set(ids([r for r in ref if r['schedule']==dict(horizon=1,a=0,b=0,order='ab')]))
 delta=[]
 for pat in patterns:
  cs={r['case'] for r in ref if r['pattern']==pat};delta.append(sum(int(c in ids(ref))-int(c in fixed) for c in cs)/len(cs))
 rng=random.Random(771);boot=sorted(sum(rng.choices(delta,k=len(delta)))/len(delta) for _ in range(5000))
 single=read('transport-grid.jsonl');singleq=read('transport-quotient.jsonl');assert len(single)==1080 and len(singleq)==270
 single_contracts=json.loads((ROOT/'fixtures/contracts.json').read_text())
 single_cases={c['id']:c for c in json.loads((ROOT/'fixtures/cases.json').read_text())}
 for r in single+singleq:
  assert r['receipt_check']['status']=='match' and len(r['server_records'])==1 and r['legacy_signature_agreement']
  assert interpret_single(r['trace'],single_contracts[r['case']])==r['oracle']
  rec=r['server_records'][0]
  if rec['contentType'].startswith('application/json'):value=json.loads(rec['body']).get('value')
  else:
   body=parse_qs(rec['body'],keep_blank_values=True)
   value=('value' in body) if single_cases[r['case']]['kind']=='checkbox' else body.get('value',[None])[0]
  assert same_value(value,r['receipt_check']['receivedValue']) and same_value(value,r['receipt_check']['observedConsumerValue'])

 challenges=read('challenges.jsonl');assert len(challenges)==20
 fallback=read('fallback.jsonl');assert len(fallback)==304
 fallback_contracts={c['id']:contracts[c['id'].replace('F','')] for c in json.loads((ROOT/'fixtures/multi/fallback-cases.json').read_text())}
 fallback_effects=json.loads(subprocess.check_output(['node','scripts/extract_effects.mjs','fixtures/multi/fallback-handlers.js'],cwd=ROOT))['effects']
 assert all(not e['known'] for e in fallback_effects.values())
 assert fallback_effects==json.loads((OUT/'fallback-effects.json').read_text())['effects']
 # Fallback is the full reference: rep 0 itself is the unreduced set, not a claimed new run.
 fallback_validation=validate_pair_runs(fallback,[r for r in fallback if r['rep']==0],{c:False for c in fallback_contracts})
 for r in challenges+fallback:
  assert not r.get('error') and not r.get('page_errors') and len(r['server_records'])==1
  receipts=[e for e in r['trace'] if e['type']=='receipt'];assert len(receipts)==1
  assert r['server_records'][0]['contentType'].startswith('application/json')
  # Type-preserving serialized equality avoids Python bool/number equivalence.
  assert json.dumps(json.loads(r['server_records'][0]['body']),sort_keys=True)==json.dumps(receipts[0]['payload'],sort_keys=True)
  c=r.get('contracts',fallback_contracts.get(r['case']))
  if 'contracts' in r:assert c==contracts['MR04' if r['framework']=='react' else 'MV04']
  assert interpret_form(r['trace'],c)==r['oracle']
  for name,value in r.get('ablations',{}).items():assert interpret_form(r['trace'],c,ablation=name)==value

 summary=dict(single_grid_runs=len(single),single_quotient_runs=len(singleq),single_counts=count(single),single_receipts=len(single)+len(singleq),single_agreement_with_legacy=True,
  multi_grid_runs=len(grid),multi_reference_runs=len(ref),multi_quotient_runs=len(quot),multi_counts_reference=count(ref),multi_counts_repeated=count(grid),multi_counts_quotient=count(quot),
  multi_violating_configs=ids(ref),multi_clean_configs=sorted(set(contracts)-set(ids(ref))),multi_state_only_runs=len(state_only),multi_state_only_configs=sorted({r['case'] for r in state_only}),
  repeat_signature_disagreements=repdiff,quotient_replay_disagreements=qdiff,within_class_disagreements=len(equivalence_bad),proposed_classes=len(groups),comparison_edges=len(ref)-len(groups),
  retained_fraction=len(quot)/len(ref),reduction_fraction=1-len(quot)/len(ref),multi_warnings=sum(bool(r.get('console')) for r in ref),multi_page_errors=sum(bool(r.get('page_errors')) for r in ref),
  pattern_clusters=len(patterns),cluster_sensitivity=dict(estimand='grid minus fixed-release config coverage, equal pattern weight; descriptive resampling only',mean=sum(delta)/len(delta),percentile_2_5=boot[124],percentile_97_5=boot[4874],replicates=5000,seed=771),
  holdout=dict(configurations=4,reference_runs=sum(r['split']=='holdout' for r in ref),violating_configs=ids([r for r in ref if r['split']=='holdout']),counts=count([r for r in ref if r['split']=='holdout'])),
  baselines=baselines,ablations=ab,cases=case_rows,challenges=dict(runs=len(challenges),counts=count(challenges)),
  validation_gate=validation,fallback=dict(runs=len(fallback),counts=count(fallback),validation=fallback_validation),
  total_receiver_backed_runs=len(single)+len(singleq)+len(grid)+len(quot)+len(challenges)+len(fallback),
  measured_meta={name:json.loads((OUT/(name+'.meta.json')).read_text()) for name in ['transport-grid','transport-quotient','multi-grid','multi-quotient','challenges','fallback']})
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
 # Every numerical manuscript table below is generated from source observations.
 def texfile(name,s): (GEN/name).write_text(s+'\n')
 def table(header,rows):
  return '\n'.join([r'\begin{tabular}{@{}lrr@{}}',r'\toprule',header+r' \\',r'\midrule',*rows,r'\bottomrule',r'\end{tabular}'])
 texfile('baselines.tex',table('Strategy or sensor & Runs & Cases',
  [f"{r['method']} & {r['runs']} & {r['detected_configurations']}/8 \\\\" for r in baselines]))
 texfile('ablations.tex',table('Removed component & Missed /172 & Extra /436',
  [f"{r['ablation'].replace('_',r'\_')} & {r['missed_reference_traces']} & {r['extra_on_reference_clean']} \\\\" for r in ab]))
 texfile('cases.tex','\n'.join(f"{r['case']} & {r['pattern']} & {r['violations']} & {r['clean']} & {r['no_edit']} & {r['state_only']} \\\\" for r in case_rows))
 nums={'SingleRuns':len(single),'SingleQuot':len(singleq),'MultiRuns':len(grid),'MultiRef':len(ref),'MultiQuot':len(quot),'MultiBad':len(ids(ref)),'MultiState':len(state_only),'MultiStateConfigs':len({r['case'] for r in state_only}),'MultiViolation':sum(bad(r) for r in ref),'MultiClean':sum(r['oracle']['status']=='clean' for r in ref),'MultiNoedit':sum(r['oracle']['status']=='no-edit' for r in ref),'Reduction':f'{100*(1-len(quot)/len(ref)):.1f}'}
 texfile('numbers.tex','\n'.join('\\newcommand{\\HK'+k+'}{'+str(v)+'}' for k,v in nums.items()))
 print(json.dumps({k:v for k,v in summary.items() if k not in ['baselines','ablations','cases','measured_meta']},indent=2))
if __name__=='__main__':run()
