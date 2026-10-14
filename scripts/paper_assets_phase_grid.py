#!/usr/bin/env python3
"""Phase-grid tables and the existing native-font Python/vector figure route.

Run normally with TeX's kpsewhich on PATH, or pass --font-root TeX/fonts
(the directory containing type1/public/libertine/LinLibertineT.pfb).
ReportLab, paper/figures/draw_coverage.py and its AFM are required; there is no
font substitution. The renderer also refreshes historical-vue.pdf from the
existing generated/native-integration/historical.csv, without reanalysis.
"""
from pathlib import Path
import argparse,importlib.util,json,csv,collections,shutil,subprocess,sys
R=Path(__file__).resolve().parents[1];P=R.parent/'paper';G=P/'generated/phase-grid';F=P/'figures'

def font_root(value):
 if value is not None:
  root=value.resolve()
 else:
  lookup=shutil.which('kpsewhich')
  if lookup is None:
   raise RuntimeError('Linux Libertine Type-1 font unavailable: pass --font-root <TeX fonts directory>')
  found=subprocess.check_output([lookup,'LinLibertineT.pfb'],text=True).strip()
  if not found:
   raise RuntimeError('kpsewhich did not find LinLibertineT.pfb; pass --font-root <TeX fonts directory>')
  root=Path(found).resolve().parents[3]
 if not (root/'type1/public/libertine/LinLibertineT.pfb').is_file():
  raise RuntimeError(f'Missing native Linux Libertine Type-1 font below {root}; no fallback')
 return root

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--font-root',type=Path,help='TeX fonts directory; otherwise resolve LinLibertineT.pfb with kpsewhich')
args=ap.parse_args()
native_font_root=font_root(args.font_root)
if importlib.util.find_spec('reportlab') is None:
 raise RuntimeError('The native-font Python figure route requires ReportLab in this Python environment')
renderer=F/'draw_coverage.py'
for dependency in (renderer,F/'libertine-labels.afm',P/'generated/native-integration/historical.csv'):
 if not dependency.is_file():
  raise RuntimeError(f'Missing native figure dependency: {dependency}')
# Require paired, non-duplicate coordinates before writing any paper assets.
with (R/'results/phase-grid/multi-budgets.csv').open(newline='') as stream:
 bud=list(csv.DictReader(stream))
coverage={strategy:{} for strategy in ('phase-grid','source-quotient')}
for row in bud:
 strategy=row['strategy'];budget=int(row['budget_per_case']);detected=int(row['cases'])
 if strategy not in coverage or budget<1 or detected<0 or budget in coverage[strategy]:
  raise ValueError('Invalid or duplicate phase-grid budget coordinate')
 coverage[strategy][budget]=detected
budgets=sorted(coverage['phase-grid'])
if not budgets or budgets!=sorted(coverage['source-quotient']):
 raise ValueError('Reference and representative budget coordinates must have the same domain')
if budgets!=[1,2,4,8,16,29,38]:
 raise ValueError('Budget domain is incompatible with the current native renderer layout')
s=json.loads((R/'results/phase-grid/summary.json').read_text());cases={c['case']:c for c in s['cases']}
if any(value>len(s['multi_violating_configs']) for series in coverage.values() for value in series.values()):
 raise ValueError('Budget coverage exceeds the source summary configuration count')
labels=['Independent adoption','Separate submit store','Coupled handlers','Reset $a$ only','Reset both; permit $a$','Keyed default replacement','Unavailable before $H$*','Declared removal of $a$*']
rows=[]
for i,label in enumerate(labels,1):
 a,b=cases[f'MR{i:02}'],cases[f'MV{i:02}']
 if a['representatives']!=b['representatives']:
  raise ValueError('Paired framework cases require the same representative count')
 rows.append(f'{label} & {a["violations"]} & {b["violations"]} & {a["representatives"]} \\\\')
(G/'patterns.tex').write_text('\n'.join(rows)+'\n')
base_labels=['Post-hydration','Fixed pre-hydration','Phase grid','Source-proposed quotient','DOM-only sensor','Production warning sensor']
(G/'baselines.tex').write_text('\n'.join(f'{name} & {r["runs"]} & {r["detected_configurations"]}/8 \\\\' for name,r in zip(base_labels,s['baselines']))+'\n')
ab_labels=['dom-only','global-reset','drop-identity','strict-node']
(G/'ablations.tex').write_text('\n'.join(f'{name} & {r["missed_reference_traces"]} & {r["extra_on_reference_clean"]} \\\\' for name,r in zip(ab_labels,s['ablations']))+'\n')
raw=[json.loads(l) for l in (R/'results/phase-grid/multi-grid.jsonl').read_text().splitlines()]
r=next(r for r in raw if r['case']=='MR02' and r['rep']==0 and r['schedule']==dict(horizon=1,a=0,b=0,order='ab'))
ev=[('Initial',r['trace'][0]),('Edited',next(e for e in r['trace'] if e['type']=='edit' and e['field']=='b')),('Hydrated',next(e for e in r['trace'] if e['type']=='checkpoint' and e['phase']=='hydrated')),('Receiver',next(e for e in r['trace'] if e['type']=='receipt'))]
rows=[]
for name,e in ev:
 vals={f['id']:f['value'] for f in e['fields']};recv='--' if 'payload' not in e else ','.join(e['payload'][k] for k in ['a','b'])
 rows.append(name+' & '+' & '.join('\\texttt{'+v+'}' for v in [vals['a'],vals['b'],recv])+' \\\\')
(G/'witness.tex').write_text('\n'.join(rows)+'\n')
with (F/'budget-coverage.csv').open('w',newline='') as stream:
 writer=csv.writer(stream,lineterminator='\n');writer.writerow(['budget','reference','representative'])
 for budget in budgets:
  writer.writerow([budget,coverage['phase-grid'][budget],coverage['source-quotient'][budget]])
(F/'budget-coverage.tex').write_text('% Retained measured-order counts in budget-coverage.csv.\n'+r'\includegraphics[width=\columnwidth]{figures/budget-coverage.pdf}'+'\n',encoding='utf-8',newline='\n')
(F/'budget-coverage-standalone.tex').write_text('\\documentclass[border=3pt]{standalone}\n\\usepackage{graphicx}\n\\begin{document}\n\\setlength{\\columnwidth}{3.35in}\n\\input{budget-coverage}\n\\end{document}\n')
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
for name in ['ownership']:
 (F/(name+'-standalone.tex')).write_text('\\documentclass[tikz,border=3pt]{standalone}\n\\usepackage{pgfplots}\n\\usetikzlibrary{arrows.meta,positioning,fit}\n\\pgfplotsset{compat=1.18}\n\\begin{document}\n\\setlength{\\columnwidth}{3.35in}\n\\input{'+name+'}\n\\end{document}\n')

# Full tabular environments avoid TeX input-boundary/noalign interactions.
for name,cols,header in [
 ('patterns','lrrr','Workflow pattern & React & Vue & $Q$'),
 ('baselines','lrr','Strategy or sensor & Runs & Cases'),
 ('ablations','lrr','Removed component & Missed /172 & Extra /436'),
 ('witness','llll','Observation & Live $a$ & Live $b$ & Received $(a,b)$')]:
 p=G/(name+'.tex');body=p.read_text();p.write_text('\\begin{tabular}{@{}'+cols+'@{}}\\toprule\n'+header+' \\\\\\midrule\n'+body+'\\bottomrule\\end{tabular}\n')

# Preserve the current renderer, native font, page geometry and historical data.
subprocess.run([sys.executable,'-B',str(renderer),'--font-root',str(native_font_root)],check=True)
print('Generated phase-grid tables, native-font Python/vector figures, and editable ownership diagram.')
