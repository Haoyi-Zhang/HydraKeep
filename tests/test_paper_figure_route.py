"""Benign generator regression checks in disposable copies, never browser runs.

The renderer stub records invocation only; actual PDF/font/layout validation is
separate. P117_FIGURE_TEST_TMP may place all disposable copies in a private root.
"""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PaperFigureRoute(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ.get('P117_FIGURE_TEST_TMP'))
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.artifact = self.base / 'artifact'
        self.paper = self.base / 'paper'
        for relative in ('scripts/paper_assets.py', 'scripts/paper_assets_phase_grid.py',
                         'results/summary.json', 'results/grid.jsonl', 'results/configurations.csv',
                         'results/phase-grid/summary.json', 'results/phase-grid/multi-grid.jsonl',
                         'results/phase-grid/multi-budgets.csv'):
            target = self.artifact / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        self.figures = self.paper / 'figures'
        self.figures.mkdir(parents=True)
        (self.paper / 'generated/phase-grid').mkdir(parents=True)
        native = self.paper / 'generated/native-integration'
        native.mkdir()
        # Owned orchestration fixtures: not PDF/font-fidelity evidence.
        (self.figures / 'libertine-labels.afm').write_text('benign AFM fixture')
        (native / 'historical.csv').write_text('family,before,after,current,total\n')
        (self.figures / 'draw_coverage.py').write_text(
            'import json,sys\nfrom pathlib import Path\n'
            'Path(__file__).with_name("renderer-call.json").write_text(json.dumps(sys.argv[1:]))\n')
        # The production renderer is not run in these orchestration checks.
        # An owned availability fixture keeps them independent of ReportLab;
        # genuine font/PDF validation runs separately with the real package.
        self.modules = self.base / 'orchestration_modules'
        self.modules.mkdir()
        (self.modules / 'reportlab.py').write_text('# Availability-only fixture; no renderer API.\n')
        self.font = self.base / 'fonts'
        pfb = self.font / 'type1/public/libertine/LinLibertineT.pfb'
        pfb.parent.mkdir(parents=True)
        pfb.write_bytes(b'benign owned font-location fixture; renderer is stubbed')

    def run_generator(self, name, *args, env=None):
        environment = os.environ.copy() if env is None else env.copy()
        environment['PYTHONPATH'] = str(self.modules)
        return subprocess.run([sys.executable, '-B', str(self.artifact / 'scripts' / name), *args],
                              cwd=self.base, capture_output=True, text=True, env=environment, timeout=30)

    def test_phase_grid_csv_and_wrapper_use_existing_native_renderer(self):
        result = self.run_generator('paper_assets_phase_grid.py', '--font-root', str(self.font))
        self.assertEqual(result.returncode, 0, result.stderr)
        with (ROOT / 'results/phase-grid/multi-budgets.csv').open(newline='') as stream:
            raw = list(csv.DictReader(stream))
        by_key = {(r['strategy'], r['budget_per_case']): r['cases'] for r in raw}
        with (self.figures / 'budget-coverage.csv').open(newline='') as stream:
            actual = list(csv.DictReader(stream))
        expected = [{'budget': str(b), 'reference': by_key[('phase-grid', str(b))],
                     'representative': by_key[('source-quotient', str(b))]}
                    for b in sorted({int(r['budget_per_case']) for r in raw})]
        self.assertEqual(actual, expected)
        wrapper = (self.figures / 'budget-coverage.tex').read_text()
        self.assertEqual(wrapper, '% Retained measured-order counts in budget-coverage.csv.\n'
                         '\\includegraphics[width=\\columnwidth]{figures/budget-coverage.pdf}\n')
        self.assertNotIn('pgfplots', (self.figures / 'budget-coverage-standalone.tex').read_text())
        self.assertEqual(json.loads((self.figures / 'renderer-call.json').read_text()),
                         ['--font-root', str(self.font.resolve())])
        self.assertIn('tikzpicture', (self.figures / 'ownership.tex').read_text())

    def test_table_names_and_counts_match_current_manuscript(self):
        result = self.run_generator('paper_assets_phase_grid.py', '--font-root', str(self.font))
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = self.paper / 'generated/phase-grid'
        baseline = (generated / 'baselines.tex').read_text()
        for row in ('Post-hydration & 16 & 0/8', 'Fixed pre-hydration & 16 & 4/8',
                    'Phase grid & 608 & 8/8', 'Source-proposed quotient & 482 & 8/8',
                    'DOM-only sensor & 608 & 7/8', 'Production warning sensor & 608 & 0/8'):
            self.assertIn(row, baseline)
        ablation = (generated / 'ablations.tex').read_text()
        for row in ('dom-only & 28 & 0', 'global-reset & 30 & 0',
                    'drop-identity & 22 & 0', 'strict-node & 0 & 0'):
            self.assertIn(row, ablation)
        for name in ('patterns', 'baselines', 'ablations'):
            table = (generated / (name + '.tex')).read_text()
            self.assertEqual(table.count('\\begin{tabular}'), 1)
            self.assertEqual(table.count('\\end{tabular}'), 1)
            self.assertNotIn('\\texttt', table)

    def test_bad_budget_coordinates_fail_before_any_output(self):
        path = self.artifact / 'results/phase-grid/multi-budgets.csv'
        original = path.read_text()
        for mode in ('duplicate', 'missing', 'unexpected', 'outside_layout'):
            with self.subTest(mode=mode):
                lines = original.splitlines()
                if mode == 'duplicate':
                    lines.append(lines[1])
                elif mode == 'missing':
                    lines.pop(1)
                elif mode == 'unexpected':
                    lines[1] = lines[1].replace('phase-grid', 'benign-unknown-strategy')
                else:
                    lines[1] = lines[1].replace(',4', ',99')
                path.write_text('\n'.join(lines) + '\n')
                result = self.run_generator('paper_assets_phase_grid.py', '--font-root', str(self.font))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.figures / 'renderer-call.json').exists())
                self.assertEqual(list((self.paper / 'generated/phase-grid').iterdir()), [])

    def test_missing_font_and_renderer_dependencies_are_explicit(self):
        result = self.run_generator('paper_assets_phase_grid.py', '--font-root', str(self.base / 'absent-font'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing native Linux Libertine Type-1 font', result.stderr)
        (self.figures / 'libertine-labels.afm').unlink()
        result = self.run_generator('paper_assets_phase_grid.py', '--font-root', str(self.font))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing native figure dependency', result.stderr)
        self.assertFalse((self.figures / 'renderer-call.json').exists())
        self.assertEqual(list((self.paper / 'generated/phase-grid').iterdir()), [])

    def test_default_font_lookup_fails_explicitly_without_tex(self):
        env = os.environ.copy()
        env['PATH'] = ''
        result = self.run_generator('paper_assets_phase_grid.py', env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pass --font-root', result.stderr)
        self.assertFalse((self.figures / 'renderer-call.json').exists())

    def test_legacy_numeric_generator_never_rewrites_statistical_figures(self):
        names = ('budget.tex', 'phases.tex', 'budget-standalone.tex', 'phases-standalone.tex',
                 'budget-coverage.tex', 'historical-vue.tex')
        for name in names:
            (self.figures / name).write_text('benign retained figure sentinel\n')
        result = self.run_generator('paper_assets.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in names:
            self.assertEqual((self.figures / name).read_text(), 'benign retained figure sentinel\n')
        self.assertEqual({p.name for p in (self.paper / 'generated').glob('*.tex')},
                         {'numbers.tex', 'corpus.tex', 'baselines.tex', 'ablations.tex', 'witness.tex'})


if __name__ == '__main__':
    unittest.main()
