#!/usr/bin/env python3
"""Validate and summarize the heterogeneous-control transaction experiment.

The validator treats browser rows as evidence, not as trusted verdicts. It
recomputes both interpreters, checks the complete factorial design, and follows
bytes from the dispatch event through the loopback receiver to the receipt event
using type-sensitive JSON equality.
"""
from __future__ import annotations
import collections
import argparse
import csv
import itertools
import json
import math
import pathlib
import statistics
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from transaction_oracle import diagnosis, interpret_transactions
from transaction_spec import specify

OUT = ROOT / 'results' / 'typed-transactions'
PAPER = ROOT.parent / 'paper' / 'generated' / 'typed-transactions'
CASES = json.loads((ROOT / 'fixtures' / 'typed-transactions' / 'cases.json').read_text())
CONTRACTS = json.loads((ROOT / 'fixtures' / 'typed-transactions' / 'contracts.json').read_text())
ABLATIONS = ('global-release', 'latest-at-receipt', 'dom-only',
             'strict-node', 'consumer-string-coercion')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def typed_json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool/int equality shortcut."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            typed_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(
            typed_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def validate(rows: list[dict[str, Any]], *, profile: str = 'full') -> dict[tuple, tuple]:
    ids = [case['id'] for case in CASES]
    if profile == 'full':
        gaps, orders, reps = ('pre', 'post'), (('t1', 't2'), ('t2', 't1')), range(2)
    elif profile == 'smoke':
        ids = [case['id'] for case in CASES if case['pattern'] in
               ('typed-snapshot', 'checkbox-coercion', 'scoped-submit', 'replacement')]
        gaps, orders, reps = ('pre',), (('t2', 't1'),), (0,)
    else:
        raise ValueError('Unknown experiment profile')
    expected = set(itertools.product(ids, gaps, orders, reps))
    cells = [(row['case'], row['gap'], tuple(row['dispatch_order']), row['rep'])
             for row in rows]
    require(len(cells) == len(set(cells)), 'Duplicate experiment cell')
    require(set(cells) == expected, 'Missing or unexpected experiment cell')

    declared = {case['id']: case for case in CASES}
    seen_runs: set[str] = set()
    repeated: dict[tuple, tuple] = {}
    for row in rows:
        require(row['run'] not in seen_runs, 'Duplicate run identity')
        seen_runs.add(row['run'])
        case = declared[row['case']]
        require(row['framework'] == case['framework'] and row['pattern'] == case['pattern'],
                'Row metadata differs from the declared case')
        require(row['evidence_class'] ==
                'offline-browser-prerender-heterogeneous-controls-loopback-http',
                'Incorrect evidence classification')
        require(not row.get('error') and not row.get('page_errors') and not row.get('console'),
                'Browser execution error or console warning')
        duration = row.get('duration_ms')
        require(type(duration) in (int, float) and math.isfinite(duration) and duration >= 0,
                'Invalid measured duration')

        contract = CONTRACTS[row['case']]
        trace = row['trace']
        result = interpret_transactions(trace, contract)
        reference = specify(trace, contract)
        require(result == row['oracle'], 'Stored monitor result differs from recomputation')
        require(reference == row['reference'], 'Stored specification result differs')
        require(diagnosis(result) == diagnosis(reference),
                'Incremental monitor and prefix specification disagree')
        require(result['status'] != 'inconclusive', 'Incomplete transaction evidence')
        require(result['accepted_edits'] == 4 and result['consumptions'] == 2
                and result['receipts'] == 2, 'Unexpected semantic evidence counts')
        edits = [event for event in trace if event.get('type') == 'edit']
        require(all(event.get('trusted') is True for event in edits),
                'Edit was not produced by a trusted browser action')

        consumes = {event['transaction']: event for event in trace
                    if event.get('type') == 'consume'}
        dispatches = [event for event in trace if event.get('type') == 'dispatch']
        receipts = [event for event in trace if event.get('type') == 'receipt']
        require(len(consumes) == len(dispatches) == len(receipts) == 2,
                'Missing or duplicate transaction events')
        require([event['transaction'] for event in receipts] == row['dispatch_order'],
                'Observed receipt order differs from the design cell')
        require(len(row.get('server_records', [])) == 2,
                'Missing or duplicate loopback receiver records')
        for receipt, record, dispatch in zip(receipts, row['server_records'], dispatches):
            tx = receipt['transaction']
            require(tx == record.get('transaction') == dispatch.get('transaction'),
                    'Transaction correspondence differs')
            require(receipt['consumer'] == record.get('consumer') ==
                    dispatch.get('consumer') == consumes[tx]['consumer'],
                    'Consumer correspondence differs')
            require(record.get('contentType', '').split(';')[0] == 'application/json',
                    'Unexpected receiver content type')
            try:
                body = json.loads(record['body'])
                dispatched = json.loads(dispatch['body'])
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError('Invalid receiver/dispatch JSON') from exc
            require(typed_json_equal(body, receipt['payload']) and
                    typed_json_equal(receipt['payload'], dispatched),
                    'Dispatch -> receiver -> receipt payload chain differs')

        repeat_key = (row['case'], row['gap'], tuple(row['dispatch_order']))
        signature = diagnosis(result)
        if repeat_key in repeated:
            require(repeated[repeat_key] == signature, 'Repeat diagnostic instability')
        else:
            repeated[repeat_key] = signature

    # The two framework implementations are paired realizations of one workflow.
    for row in rows:
        if row['framework'] != 'react':
            continue
        counterpart = 'HTV' + row['case'][3:]
        left = repeated[(row['case'], row['gap'], tuple(row['dispatch_order']))]
        right = repeated[(counterpart, row['gap'], tuple(row['dispatch_order']))]
        require(left == right, 'Paired React/Vue diagnostic disagreement')
    return repeated


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    validate(rows)
    workflow_rows = []
    for pattern in dict.fromkeys(case['pattern'] for case in CASES):
        subset = [row for row in rows if row['pattern'] == pattern]
        counts = collections.Counter(row['oracle']['status'] for row in subset)
        consumer_only = sum(
            any(failure['kind'] == 'consumer-only-loss'
                for failure in row['oracle']['failures']) and
            not any(failure['kind'] == 'display-loss'
                    for failure in row['oracle']['failures'])
            for row in subset)
        workflow_rows.append({
            'workflow': pattern,
            'runs': len(subset),
            'clean': counts['clean'],
            'violation': counts['violation'],
            'consumer_only': consumer_only,
            'median_ms': round(statistics.median(row['duration_ms'] for row in subset), 3),
        })

    ablation_rows = []
    for variant in ABLATIONS:
        false_negative = false_positive = inconclusive = changed = 0
        by_pattern: collections.Counter[str] = collections.Counter()
        for row in rows:
            value = interpret_transactions(
                row['trace'], CONTRACTS[row['case']], ablation=variant)
            base = row['oracle']
            false_negative += base['status'] == 'violation' and value['status'] == 'clean'
            false_positive += base['status'] == 'clean' and value['status'] == 'violation'
            inconclusive += value['status'] == 'inconclusive'
            if diagnosis(value) != diagnosis(base):
                changed += 1
                by_pattern[row['pattern']] += 1
        ablation_rows.append({
            'variant': variant,
            'missed_violating_traces': false_negative,
            'false_alarms_on_clean_traces': false_positive,
            'inconclusive': inconclusive,
            'changed_diagnostics': changed,
            'affected_workflows': ';'.join(
                f'{name}:{count}' for name, count in sorted(by_pattern.items())),
        })

    status = collections.Counter(row['oracle']['status'] for row in rows)
    failures = collections.Counter(
        failure['kind'] for row in rows for failure in row['oracle']['failures'])
    return {
        'primary_browser_runs': len(rows),
        'loopback_http_receipts': sum(len(row['server_records']) for row in rows),
        'paired_framework_configurations': len(CASES),
        'workflow_designs': len(workflow_rows),
        'unique_schedule_cells': len(rows) // 2,
        'repeated_cell_checks': len(rows) // 2,
        'repeat_diagnostic_disagreements': 0,
        'prefix_specification_disagreements': 0,
        'status_counts': dict(status),
        'failure_kind_counts': dict(failures),
        'consumer_only_violating_runs': sum(row['consumer_only'] for row in workflow_rows),
        'workflows': workflow_rows,
        'ablations': ablation_rows,
        'scope': ('authored heterogeneous-control workflows in real Chromium with '
                  'trusted text/checkbox/select actions and loopback JSON receipts'),
    }


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=('full', 'smoke'), default='full')
    parser.add_argument('--input', type=pathlib.Path)
    args = parser.parse_args()
    input_path = args.input or OUT / ('smoke.jsonl' if args.profile == 'smoke' else 'runs.jsonl')
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    rows = [json.loads(line) for line in input_path.read_text().splitlines()
            if line.strip()]
    if args.profile == 'smoke':
        validate(rows, profile='smoke')
        report = {'profile': 'smoke', 'validated_rows': len(rows),
                  'validated_receipts': sum(len(row['server_records']) for row in rows),
                  'status_counts': dict(collections.Counter(row['oracle']['status'] for row in rows))}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'smoke.summary.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return
    report = summarize(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    PAPER.mkdir(parents=True, exist_ok=True)
    (OUT / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    for name, values in (('workflows.csv', report['workflows']),
                         ('ablations.csv', report['ablations'])):
        write_csv(OUT / name, values)
        write_csv(PAPER / name, values)

    macros = {
        'TypedRuns': report['primary_browser_runs'],
        'TypedReceipts': report['loopback_http_receipts'],
        'TypedClean': report['status_counts'].get('clean', 0),
        'TypedBad': report['status_counts'].get('violation', 0),
        'TypedSinkOnly': report['consumer_only_violating_runs'],
        'TypedWorkflows': report['workflow_designs'],
    }
    (PAPER / 'numbers.tex').write_text('\n'.join(
        f'\\newcommand{{\\{name}}}{{{value}}}' for name, value in macros.items()) + '\n')

    labels = {
        'global-release': 'Global display release',
        'latest-at-receipt': 'Latest value at receipt',
        'dom-only': 'Display-only oracle',
        'strict-node': 'Physical-node identity',
        'consumer-string-coercion': 'String-coerced payloads',
    }
    lines = ['\\begin{tabular}{@{}lrr@{}}', '\\toprule',
             'Ablated rule & Missed & False alarms \\\\', '\\midrule']
    for row in report['ablations']:
        lines.append(f"{labels[row['variant']]} & {row['missed_violating_traces']} & {row['false_alarms_on_clean_traces']} " + r'\\')
    lines += ['\\bottomrule', '\\end{tabular}']
    (PAPER / 'ablations.tex').write_text('\n'.join(lines) + '\n')

    earlier = json.loads((ROOT / 'results' / 'transactions' / 'summary.json').read_text())
    old = earlier['browser_counts']
    profile_lines = [
        '\\begin{tabular}{@{}lrrrr@{}}', '\\toprule',
        'Profile & Runs & Clean & Bad & Sink only \\\\', '\\midrule',
        f"Two text fields & {earlier['primary_browser_runs']} & {old.get('clean', 0)} & {old.get('violation', 0)} & {earlier['consumer_only_violating_runs']} " + r'\\',
        f"Text/check/select & {report['primary_browser_runs']} & {report['status_counts'].get('clean', 0)} & {report['status_counts'].get('violation', 0)} & {report['consumer_only_violating_runs']} " + r'\\',
        '\\bottomrule', '\\end{tabular}',
    ]
    (PAPER / 'profiles.tex').write_text('\n'.join(profile_lines) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
