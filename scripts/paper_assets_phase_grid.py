#!/usr/bin/env python3
"""All phase-grid quantitative tables and plotted coordinates from actual outputs."""
from pathlib import Path
import json,csv,collections
R=Path(__file__).resolve().parents[1];P=R.parent/'paper';G=P/'generated/phase-grid';F=P/'figures'
s=json.loads((R/'results/phase-grid/summary.json').read_text());cases={c['case']:c for c in s['cases']}
labels=['Independent adoption','Separate submit store','Coupled handlers','Reset $a$ only','Reset both; permit $a$','Keyed default replacement','Unavailable before $H$*','Declared removal of $a$*']
rows=[]
for i,label in enumerate(labels,1):
 a,b=cases[f'MR{i:02}'],cases[f'MV{i:02}'];assert a['representatives']==b['representatives'];rows.append(f'{label} & {a["violations"]} & {b["violations"]} & {a["representatives"]} \\\\')
(G/'patterns.tex').write_text('\n'.join(rows)+'\n')
base_labels=['Post-hydration + contract','Fixed release + contract','Phase grid + contract','Source-proposed set','DOM-only sensor','Production warnings']
(G/'baselines.tex').write_text('\n'.join(f'{name} & {r["runs"]} & {r["detected_configurations"]}/8 \\\\' for name,r in zip(base_labels,s['baselines']))+'\n')
ab_labels=['No consumer check','Whole-form reset permission','Forget replaced node','Require physical continuity']
(G/'ablations.tex').write_text('\n'.join(f'{name} & {r["missed_reference_traces"]} & {r["extra_on_reference_clean"]} \\\\' for name,r in zip(ab_labels,s['ablations']))+'\n')
raw=[json.loads(l) for l in (R/'results/phase-grid/multi-grid.jsonl').read_text().splitlines()]
r=next(r for r in raw if r['case']=='MR02' and r['rep']==0 and r['schedule']==dict(horizon=1,a=0,b=0,order='ab'))
ev=[('Initial',r['trace'][0]),('Edited',next(e for e in r['trace'] if e['type']=='edit' and e['field']=='b')),('Hydrated',next(e for e in r['trace'] if e['type']=='checkpoint' and e['phase']=='hydrated')),('Receiver',next(e for e in r['trace'] if e['type']=='receipt'))]
rows=[]
for name,e in ev:
 vals={f['id']:f['value'] for f in e['fields']};recv='--' if 'payload' not in e else ','.join(e['payload'][k] for k in ['a','b'])
 rows.append(name+' & '+' & '.join('\\texttt{'+v+'}' for v in [vals['a'],vals['b'],recv])+' \\\\')
(G/'witness.tex').write_text('\n'.join(rows)+'\n')
bud=list(csv.DictReader((R/'results/phase-grid/multi-budgets.csv').open()));coords=[]
for strategy in ['phase-grid','source-quotient']:
 coords.append(' '.join('('+r['budget_per_case']+','+r['cases']+')' for r in bud if r['strategy']==strategy))
(F/'budget-coverage.tex').write_text(r'''\begin{tikzpicture}
\begin{axis}[
width=\columnwidth,height=4.3cm,
ybar,bar width=6pt,
symbolic x coords={1,2,4,8,16,29,38},xtick=data,
xlabel={Maximum runs per configuration},ylabel={Detected configurations},
ymin=0,ymax=8.6,ytick={0,2,4,6,8},enlarge x limits=.1,
ymajorgrids,grid style={draw=gray!20},axis line style={draw=gray!65},
legend style={font=\footnotesize,draw=none,at={(.5,1.04)},anchor=south,legend columns=2},
tick label style={font=\small},label style={font=\small}]
\addplot[area legend,fill=blue!62!black,draw=blue!62!black] coordinates {'''+coords[0]+r'''};
\addlegendentry{Reference order}
\addplot[area legend,fill=orange!78,draw=orange!78!black] coordinates {'''+coords[1]+r'''};
\addlegendentry{Representative order}
\end{axis}
\end{tikzpicture}
''')
# Conceptual figure: no quantitative data or claimed measured state invented.
(F/'ownership.tex').write_text(r'''\begin{tikzpicture}[>=Latex,node distance=5mm and 9mm,every node/.style={font=\footnotesize},box/.style={draw,rounded corners=2pt,align=center,minimum height=9mm,text width=27mm,inner sep=3pt}]
\node[box] (a) {Edit $a$ accepted\\epoch 0 active};
\node[box,right=of a] (b) {Edit $b$ accepted\\epoch 0 active};
\node[box,below=of a] (ar) {Reset permitted\\for $a$ only};
\node[box,below=of b] (br) {$b$ remains\\obligated};
\node[box,below=of ar] (ae) {New edit to $a$\\epoch 1 active};
\node[box,below=of br] (be) {Same logical $b$\\across replacement};
\node[draw,rounded corners=2pt,align=center,below=7mm of ae.south east,anchor=north,text width=64mm,inner sep=4pt] (sink) {Check live values at consumption\\Freeze each field's obligation\\Check the received payload\\by field and ownership epoch};
\draw[->] (a)--(ar);\draw[->] (ar)--(ae);\draw[->] (b)--(br);\draw[->] (br)--(be);
\draw[->] (ae.south)--(ae.south |- sink.north);\draw[->] (be.south)--(be.south |- sink.north);
\end{tikzpicture}
''')
for name in ['budget-coverage','ownership']:
 (F/(name+'-standalone.tex')).write_text('\\documentclass[tikz,border=3pt]{standalone}\n\\usepackage{pgfplots}\n\\usetikzlibrary{arrows.meta,positioning,fit}\n\\pgfplotsset{compat=1.18}\n\\begin{document}\n\\setlength{\\columnwidth}{3.35in}\n\\input{'+name+'}\n\\end{document}\n')
print('Generated phase-grid tables, actual-data budget plot, and editable conceptual diagram.')

# Full tabular environments avoid TeX input-boundary/noalign interactions.
for name,cols,header in [
 ('patterns','lrrr','Workflow pattern & React & Vue & $Q$'),
 ('baselines','lrr','Strategy or sensor & Runs & Cases'),
 ('ablations','lrr','Removed/changed component & Missed /172 & Extra /436'),
 ('witness','llll','Observation & Live $a$ & Live $b$ & Received $(a,b)$')]:
 p=G/(name+'.tex');body=p.read_text();p.write_text('\\begin{tabular}{@{}'+cols+'@{}}\\toprule\n'+header+' \\\\\\midrule\n'+body+'\\bottomrule\\end{tabular}\n')
