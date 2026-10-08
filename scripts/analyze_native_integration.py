#!/usr/bin/env python3
"""Fail-closed native evidence validation and manuscript assets from JSONL."""
from __future__ import annotations
if not __debug__: raise RuntimeError('Evidence analysis must not run with Python -O')
import collections,hashlib,itertools,json,pathlib,subprocess,sys
from urllib.parse import parse_qs
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from form_oracle import interpret_form,signature
from multi_explorer import PairSchedule,pair_grid,pair_quotient,representative,independent
from validation import validate_pair_runs
OUT=ROOT/'results/native-integration';GEN=ROOT.parent/'paper/generated/native-integration';GEN.mkdir(exist_ok=True,parents=True)
def read(name):return [json.loads(l) for l in (OUT/(name+'.jsonl')).read_text().splitlines()]
def load(p):return json.loads((ROOT/p).read_text())
def counts(rows):return dict(collections.Counter(r['oracle']['status'] for r in rows))
def sk(r):return PairSchedule(**r['schedule'])
def native_check(rows,contracts,cases):
 seen=set()
 versions={'original':{'react':'19.1.1','vue':'3.5.13'},'before':{'vue':'3.5.40'},'after':{'vue':'3.5.41'},'current':{'vue':'3.5.43'}}
 for r in rows:
  assert not r.get('error') and not r.get('page_errors') and not r['oracle']['unknown']
  assert r['run'] not in seen;seen.add(r['run'])
  doc=r['document'];assert doc['markup_sha256']==hashlib.sha256(doc['markup'].encode()).hexdigest()
  assert doc['version']==versions[r['version_tag']][r['framework']]
  assert r['evidence_class']=='native-ssr-http-navigation' and r['url'].startswith('http://127.0.0.1:')
  assert len(r['server_records'])==1
  rec=r['server_records'][0];assert rec['run']==r['run']
  receipt=[e for e in r['trace'] if e['type']=='receipt'];assert len(receipt)==1
  if r['native_submit']:
   assert rec['contentType'].startswith('application/x-www-form-urlencoded') and receipt[0]['channel']=='native'
   body=parse_qs(rec['body'],keep_blank_values=True)
   expected={f['id']:(f['id'] in body if f['kind']=='checkbox' else body.get(f['id'],[None])[0]) for f in cases[r['case']]['fields']}
  else:
   assert rec['contentType'].startswith('application/json') and receipt[0]['channel']=='application'
   expected=json.loads(rec['body'])
  assert json.dumps(expected,sort_keys=True)==json.dumps(receipt[0]['payload'],sort_keys=True)
  assert interpret_form(r['trace'],contracts[r['case']])==r['oracle']
def coverage(rows,case_ids,tags,schedules,reps):
 actual=[(r['case'],r['mode'],r['version_tag'],r['rep'],sk(r)) for r in rows]
 expected=set(itertools.product(case_ids,['development','production'],tags,range(reps),schedules))
 assert len(set(actual))==len(actual) and set(actual)==expected,'missing/duplicate/unexpected native schedule'
 return dict(rows=len(actual),configurations=len(case_ids),schedules_per_configuration=len(schedules),builds=2,versions=len(tags),repetitions=reps)
def main():
 cases={c['id']:c for c in load('fixtures/multi/cases.json')};histcases={c['id']:c for c in load('fixtures/native/historical-cases.json')};contracts=load('fixtures/multi/contracts.json');hc=load('fixtures/native/historical-contracts.json');nc=load('fixtures/native/native-submit-contracts.json')
 matrix=read('matrix-chromium');quotient=read('matrix-quotient-chromium');versions=read('versions-chromium');historical=read('historical-chromium');native=read('native-submit-chromium')
 for rows,cs,configs in [(matrix,contracts,cases),(quotient,contracts,cases),(versions,contracts,cases),(historical,hc,histcases),(native,nc,cases)]:native_check(rows,cs,configs)
 hs=[PairSchedule(1,a,b,'ab' if a<=b else 'ba') for a in [0,1] for b in [0,1]]+[PairSchedule(2,0,0,'ab'),PairSchedule(2,2,2,'ab')]
 ns=[PairSchedule(0,0,0,'ab')]+[s for s in pair_grid() if s.horizon==1]
 cov={n:coverage(rows,ids,tags,schedules,reps) for n,rows,ids,tags,schedules,reps in [
 ('matrix',matrix,sorted(cases),['original'],pair_grid(),1),('versions',versions,[c for c in cases if c.startswith('MV')],['before','after','current'],pair_grid(),1),('historical',historical,sorted(histcases),['before','after','current'],hs,2),('native-submit',native,sorted(nc),['original'],ns,1)]}
 m={(r['case'],r['mode'],sk(r)):r for r in matrix}
 legacy=[json.loads(l) for l in (ROOT/'results/phase-grid/multi-grid.jsonl').read_text().splitlines() if json.loads(l)['rep']==0]
 legacy_map={(r['case'],sk(r)):r for r in legacy}
 assert len(legacy_map)==608
 assert all(signature(r['oracle'])==signature(legacy_map[(r['case'],sk(r))]['oracle']) for r in matrix),'native/legacy diagnostic mismatch'
 assert all(signature(r['oracle'])==signature(m[(r['case'],'development',sk(r))]['oracle']) for r in matrix),'native build diagnostic mismatch'
 assert all(signature(r['oracle'])==signature(m[(r['case'],r['mode'],sk(r))]['oracle']) for r in versions),'pinned-version matrix mismatch'
 manifest=load('vendor/native/manifest.json')
 for item in manifest:assert hashlib.sha256((ROOT/'vendor/native'/item['name']).read_bytes()).hexdigest()==item['sha256']
 effects=json.loads(subprocess.check_output(['node','scripts/extract_effects.mjs','fixtures/multi/handlers.js'],cwd=ROOT))['effects']
 proposed={c:independent(effects,v['handlers']['a'],v['handlers']['b']) for c,v in cases.items()}
 reductions={}
 for mode in ['development','production']:
  groups=collections.defaultdict(list)
  for r in matrix:
   if r['mode']==mode:
    assert r['source_independent'] is proposed[r['case']]
    groups[(r['case'],representative(sk(r),proposed[r['case']]))].append(r)
  assert all(len({signature(r['oracle']) for r in g})==1 for g in groups.values())
  qrows=[r for r in quotient if r['mode']==mode]
  checked=validate_pair_runs([r for r in matrix if r['mode']==mode],qrows,proposed,repetitions=1)
  assert all(r['mode'] in ['development','production'] and r['version_tag']=='original' for r in quotient)
  reductions[mode]={'classes':len(groups),'omitted_comparisons':608-len(groups),'within_class_disagreements':0,'separate_native_representative_replay':True,'replay_validation':checked}
 hmap={(r['case'],r['mode'],r['version_tag'],sk(r)):r for r in historical if r['rep']==0}
 assert all(signature(r['oracle'])==signature(hmap[(r['case'],r['mode'],r['version_tag'],sk(r))]['oracle']) for r in historical)
 assert all(signature(r['oracle'])==signature(hmap[(r['case'],'development',r['version_tag'],sk(r))]['oracle']) for r in historical)
 ht=[]
 for case in sorted(histcases):
  values={tag:sum(r['oracle']['status']=='violation' for r in historical if r['case']==case and r['version_tag']==tag) for tag in ['before','after','current']}
  ht.append({'case':case,'runs_per_version':24,**values})
 public=read('public-production')+read('public-development');valid=[];screened=[]
 for mode in ['production','development']:
  rows=[r for r in public if r['mode']==mode];actual=[(r['rep'],tuple(r['gaps'].values())) for r in rows];assert len(set(actual))==16 and set(actual)==set(itertools.product(range(2),itertools.product([0,1],repeat=3)))
 for r in public:
  assert r['native_markup'] and not r.get('error') and not r['page_errors']
  if r['oracle']['status']=='not-evaluated':
   assert not r.get('server_records') and any(e['type']=='edit-blocked' and e['reason']=='not visible' for e in r['trace']);screened.append(r);continue
  assert len(r['server_records'])==1 and r['server_records'][0]['run']==r['run']
  receipt=[e for e in r['trace'] if e['type']=='receipt'];assert len(receipt)==1 and json.dumps(receipt[0]['payload'],sort_keys=True)==json.dumps(r['server_records'][0]['payload'],sort_keys=True)
  assert len([e for e in r['trace'] if e['type']=='consume'])==1
  pc={f:{'channel':'application'} for f in ['username','password','remember']};assert interpret_form(r['trace'],pc)==r['oracle']
  assert r['oracle']['status']=='clean' and r['form_removed'];valid.append(r)
 receipt_time_public=[interpret_form([e for e in r['trace'] if e['type']!='consume'],{f:{'channel':'application'} for f in ['username','password','remember']}) for r in valid]
 assert all(o['status']=='violation' and any(f['kind']=='dom-loss' for f in o['failures']) for o in receipt_time_public)
 controls=read('initracer-controls');assert len(controls)==16
 for r in controls:
  assert not r.get('error') and 'error' not in r and not r['page_errors'] and len(r['server_records'])==1
  payload=json.loads(r['server_records'][0]['body']);assert payload==next(e['payload'] for e in r['trace'] if e['type']=='receipt')
  assert interpret_form(r['trace'],{'a':{'channel':'application','resets':['reset']}})==r['oracle']
 control_summary=[]
 for c in ['overwrite','shadow','adopt','reset']:
  rr=[r for r in controls if r['case']==c];obs=[r for r in rr if r['mode']=='observation'];assert len(obs)==2
  report_counts=[len(r['initracer']['report']['formInputOverwrittenRaces']) for r in obs];assert len(set(report_counts))==1
  assert len({signature(r['oracle']) for r in rr})==1
  control_summary.append({'case':c,'receiver_runs':len(rr),'monitor_status':rr[0]['oracle']['status'],'initracer_overwrite_reports_per_observation_run':report_counts[0]})
 retained_total=load('results/phase-grid/summary.json')['total_receiver_backed_runs']
 summary={'study':'native-integration','closest_tool_controls':control_summary,'closest_tool_receiver_backed_runs':16,'coverage':cov,'native_matrix_counts':counts(matrix),'native_quotient_runs':len(quotient),'native_quotient_counts':counts(quotient),'native_counts_by_build':{b:counts([r for r in matrix if r['mode']==b]) for b in ['development','production']},'native_legacy_signature_disagreements':0,'native_build_signature_disagreements':0,'native_reduction_validation':reductions,'version_matrix_counts':counts(versions),'version_matrix_signature_disagreements':0,'historical_counts':counts(historical),'historical_repeat_signature_disagreements':0,'historical_build_signature_disagreements':0,'historical_families':ht,'native_submission_counts':counts(native),'native_pre_hydration_counts':counts([r for r in native if sk(r).horizon==0]),'public_profiles':len(public),'public_completed_receipts':len(valid),'receipt_time_only_flags_on_clean_public_traces':len(receipt_time_public),'public_unavailable_profiles':len(screened),'public_counts_by_build':{b:counts([r for r in public if r['mode']==b]) for b in ['development','production']},'new_complete_receiver_backed_runs':len(matrix)+len(quotient)+len(versions)+len(historical)+len(native)+len(valid),'complete_receiver_backed_runs_with_phase_grid':retained_total+len(matrix)+len(quotient)+len(versions)+len(historical)+len(native)+len(valid),'browser':'Chromium 143.0.7499.0','concurrency_note':'Experiments overlapped; wall-time ratios are not speedups.'}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 def tex(name,s):(GEN/name).write_text(s+'\n')
 tex('numbers.tex','\n'.join('\\newcommand{\\HKNative'+k+'}{'+(f'{v:,}' if isinstance(v,int) else str(v))+'}' for k,v in {'Matrix':len(matrix),'Quotient':len(quotient),'Versions':len(versions),'Historical':len(historical),'Submit':len(native),'Public':len(valid),'Unavailable':len(screened),'New':summary['new_complete_receiver_backed_runs'],'Total':summary['complete_receiver_backed_runs_with_phase_grid']}.items()))
 tex('historical.tex','\\begin{tabular}{lrrrr}\n\\toprule Control & Runs/version & 3.5.40 & 3.5.41 & 3.5.43 \\\\\n\\midrule\n'+'\n'.join(f"{r['case'].replace('HV-','')} & {r['runs_per_version']} & {r['before']} & {r['after']} & {r['current']} \\\\" for r in ht)+'\n\\bottomrule\n\\end{tabular}')
 tex('native-studies.tex','\\begin{tabular}{lrrr}\n\\toprule Study & Runs & Receipts & Violations \\\\\n\\midrule\n'+ '\n'.join(f'{label} & {len(rows):,} & {len(rows):,} & {sum(r["oracle"]["status"]=="violation" for r in rows):,} \\\\' for label,rows in [('Native reference',matrix),('Native representatives',quotient),('Version stability',versions),('Reported fix',historical),('Native form POST',native),('Public example',valid)])+'\n\\bottomrule\n\\end{tabular}')
 tex('historical.csv','family,before,after,current,total\n'+'\n'.join(','.join(str(r[x]) for x in ['case','before','after','current','runs_per_version']).replace('HV-','') for r in ht))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
