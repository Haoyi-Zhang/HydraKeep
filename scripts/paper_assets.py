#!/usr/bin/env python3
"""Create LaTeX tables, numbers and editable PGFPlots from measured JSON/CSV."""
import json,csv,pathlib,collections
ROOT=pathlib.Path(__file__).resolve().parents[1];PAPER=ROOT.parent/'paper';GEN=PAPER/'generated';FIG=PAPER/'figures';GEN.mkdir(exist_ok=True);FIG.mkdir(exist_ok=True)
s=json.loads((ROOT/'results/summary.json').read_text())
rows=[json.loads(l) for l in (ROOT/'results/grid.jsonl').read_text().splitlines()];base=[r for r in rows if r['rep']==0]
lookup={(r['case'],r['horizon'],r['gap']):r for r in base}
config=list(csv.DictReader((ROOT/'results/configurations.csv').open()));cm={r['case']:r for r in config}
def esc(x):return str(x).replace('_',r'\_').replace('&',r'\&').replace('%',r'\%')
def write(name,text): (GEN/name).write_text(text+'\n')
macros={'HKConfigs':30,'HKGridSchedules':540,'HKGridRuns':1080,'HKQuotientRuns':270,'HKViolating':s['violating_configurations'],'HKCleanConfigs':s['nonviolating_configurations'],'HKViolationRuns':s['counts_reference']['violation'],'HKCleanRuns':s['counts_reference']['clean'],'HKNoEditRuns':s['counts_reference']['no-edit'],'HKStateOnly':s['state_only_runs'],'HKRepeatDiff':s['repeat_signature_disagreements'],'HKEquivDiff':s['equivalence_signature_disagreements'],'HKGridWall':f"{s['grid_meta']['wall_seconds']:.2f}",'HKQuotientWall':f"{s['separate_quotient']['meta']['wall_seconds']:.2f}"}
write('numbers.tex','\n'.join('\\newcommand{\\'+k+'}{'+str(v)+'}' for k,v in macros.items()))
labels=['Text, state binding','Textarea, state binding','Checkbox, state binding','Select, state binding','Text, native channel / static default','Text, DOM adoption','Text, disabled until hydration','Text, client authority','Checkbox, explicit user reset','Text, keyed managed replacement','Text, separate submission store','Select, native channel / static default','Select, declared removal']
out=['\\begin{tabular}{@{}llrr@{}}','\\toprule','IDs & Workflow & React & Vue \\\\','\\midrule']
for i,label in enumerate(labels,1):
    a=cm[f'R{i:02}'];b=cm[f'V{i:02}'];out.append(f'{i:02} & {label} & {a["violating"]}/18 & {b["violating"]}/18 \\\\')
out+=['\\midrule','R14 & Textarea, native channel (holdout) & '+cm['R14']['violating']+'/18 & -- \\\\','R15 & Text, keyed default (seeded holdout) & '+cm['R15']['violating']+'/18 & -- \\\\','V14 & Checkbox, DOM adoption (holdout) & -- & '+cm['V14']['violating']+'/18 \\\\','V15 & Select, disabled (holdout) & -- & '+cm['V15']['violating']+'/18 \\\\','\\bottomrule','\\end{tabular}']
write('corpus.tex','\n'.join(out))
out=['\\begin{tabular}{@{}lrrr@{}}','\\toprule','Strategy or sensor & Runs & Cases & Run time (s) \\\\','\\midrule']
short={'Fixed release, contract oracle':'Fixed release + contract','Production warning sensor':'Production warnings','DOM-only contract sensor':'DOM-only contract'}
for b in s['baseline']:out.append(f'{short.get(b["method"],b["method"])} & {b["runs"]} & {b["detected_configurations"]}/20 & {b["sum_measured_run_seconds"]:.2f} \\\\')
out+=['\\bottomrule','\\end{tabular}'];write('baselines.tex','\n'.join(out))
out=['\\begin{tabular}{@{}lrr@{}}','\\toprule','Oracle ablation & Missed / 189 & Extra / 351 \\\\','\\midrule']
for a in s['ablations']:out.append(f'{esc(a["ablation"])} & {a["missed_reference_runs"]} & {a["extra_flags_on_reference_clean_runs"]} \\\\')
out+=['\\bottomrule','\\end{tabular}'];write('ablations.tex','\n'.join(out))
# An actual measured React input witness at H and C. No conceptual values invented.
out=['\\begin{tabular}{@{}llll@{}}','\\toprule','Observation & DOM property & App. state & App. intent \\\\','\\midrule']
r=lookup[('R01','H',0)];chosen=[]
for title,typ,phase in [('Edited','edit-complete','server-visible'),('Hydrated','checkpoint','hydrated')]:
    e=next(e for e in r['trace'] if e['type']==typ and e['phase']==phase);chosen.append((title,e,'--'))
post=next(e for e in r['trace'] if e['type']=='application-intent');chosen.append(('Submit at H',post,post['submittedValue']))
r=lookup[('R01','C',0)];e=next(e for e in r['trace'] if e['type']=='checkpoint' and e['phase']=='committed');chosen.append(('First commit',e,'--'))
for title,e,intent in chosen:
    vals=[e['fields'][0]['value'],e.get('appValue'),intent]
    out.append(title+' & '+' & '.join('\\texttt{'+esc('--' if v is None else v)+'}' for v in vals)+' \\\\')
out+=['\\bottomrule','\\end{tabular}'];write('witness.tex','\n'.join(out))
# Cost and budget plot data remain explicit, editable coordinates.
coords=[]
for name in ['phase-order','manual-hint-order']:
    coords.append(' '.join(f'({b["budget_per_configuration"]},{b["detected_configurations"]})' for b in s['budget'] if b['order']==name))
(FIG/'budget.tex').write_text(r'''\begin{tikzpicture}
\begin{axis}[width=\columnwidth,height=4.8cm,xlabel={Runs per configuration},ylabel={Detected configurations},xmin=.7,xmax=9.3,ymin=17.5,ymax=20.5,xtick={1,2,3,4,5,6,7,8,9},ytick={18,19,20},legend style={font=\scriptsize,at={(.98,.04)},anchor=south east},tick label style={font=\scriptsize},label style={font=\small}]
\addplot+[mark=o] coordinates {'''+coords[0]+r'''};
\addlegendentry{Phase order}
\addplot+[mark=triangle*,dashed] coordinates {'''+coords[1]+r'''};
\addlegendentry{Manual hint order}
\end{axis}
\end{tikzpicture}
''')
# Counts identify the earliest observed failing checkpoint, not a causal fault locator.
phase=s['first_failure_phase'];(FIG/'phases.tex').write_text(r'''\begin{tikzpicture}
\begin{axis}[ybar,width=\columnwidth,height=4.5cm,ymin=0,ymax=140,ylabel={Reference traces},symbolic x coords={H,C,T},xtick=data,xlabel={First failing observed phase},nodes near coords,bar width=22pt,tick label style={font=\scriptsize},label style={font=\small}]
\addplot coordinates {'''+f'(H,{phase.get("hydrated",0)}) (C,{phase.get("committed",0)}) (T,{phase.get("transitioned",0)})'+r'''};
\end{axis}
\end{tikzpicture}
''')
# Standalone native vector PDFs can be rebuilt without rasterization.
for name in ['budget','phases']:
    (FIG/(name+'-standalone.tex')).write_text('\\documentclass[tikz,border=3pt]{standalone}\n\\usepackage{pgfplots}\n\\pgfplotsset{compat=1.18}\n\\begin{document}\n\\setlength{\\columnwidth}{3.35in}\n\\input{'+name+'.tex}\n\\end{document}\n')
print('Regenerated paper numbers, four tables and two PGFPlots from actual results.')
