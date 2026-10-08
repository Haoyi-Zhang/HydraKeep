#!/usr/bin/env python3
"""Generate deletion-1-minimal semantic witnesses from all violating browser rows."""
from __future__ import annotations
import collections
import argparse
import json
import pathlib
import statistics
import sys
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from transaction_oracle import diagnosis, interpret_transactions
from transaction_spec import specify
from witness import ObligationWitness, failure_key

OUT = ROOT / 'results' / 'witnesses'
SOURCES = [
    ('transactions', ROOT / 'results' / 'transactions' / 'transactions.jsonl',
     ROOT / 'fixtures' / 'transactions' / 'contracts.json'),
    ('typed-transactions', ROOT / 'results' / 'typed-transactions' / 'runs.jsonl',
     ROOT / 'fixtures' / 'typed-transactions' / 'contracts.json'),
]


def load_rows(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=pathlib.Path, default=OUT)
    parser.add_argument('--paper-dir', type=pathlib.Path)
    args = parser.parse_args()
    out = args.out
    started = time.time_ns()
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    with (out / 'witnesses.jsonl').open('w') as stream:
        for family, row_path, contract_path in SOURCES:
            contracts = json.loads(contract_path.read_text())
            for row in load_rows(row_path):
                if row['oracle']['status'] != 'violation':
                    continue
                # Preserve the first recorded semantic failure. Ordering is the
                # monitor's deterministic event order, not a severity ranking.
                target = failure_key(row['oracle']['failures'][0])
                reducer = ObligationWitness(contracts[row['case']], target)
                result = reducer.minimize(row['trace'])
                reduced = list(result.events)
                monitor = interpret_transactions(reduced, contracts[row['case']])
                reference = specify(reduced, contracts[row['case']])
                if diagnosis(monitor) != diagnosis(reference):
                    raise AssertionError('Reduced witness interpreter disagreement')
                item = {
                    'family': family,
                    'run': row['run'],
                    'case': row['case'],
                    'framework': row['framework'],
                    'pattern': row['pattern'],
                    'target': {
                        'field': target[0], 'kind': target[1], 'phase': target[2],
                        'epoch': target[3], 'revision': target[4],
                        'transaction': target[5],
                    },
                    'original_events': len(row['trace']),
                    'witness_events': len(reduced),
                    'removed_events': len(row['trace']) - len(reduced),
                    'reduction_fraction': round(
                        1 - len(reduced) / len(row['trace']), 6),
                    'predicate_evaluations': result.predicate_evaluations,
                    'predicate_cache_hits': result.predicate_cache_hits,
                    'one_minimal': result.one_minimal,
                    'original_indices': list(result.indices),
                    'diagnosis': {
                        'status': monitor['status'],
                        'failure_keys': [list(key) for key in sorted(
                            failure_key(failure) for failure in monitor['failures'])],
                    },
                    'events': reduced,
                }
                records.append(item)
                stream.write(json.dumps(item, separators=(',', ':')) + '\n')

    if not records:
        raise RuntimeError('No violating browser traces were available')
    groups = {}
    for family in dict.fromkeys(record['family'] for record in records):
        subset = [record for record in records if record['family'] == family]
        groups[family] = {
            'witnesses': len(subset),
            'median_original_events': statistics.median(
                record['original_events'] for record in subset),
            'median_witness_events': statistics.median(
                record['witness_events'] for record in subset),
            'median_reduction_percent': round(100 * statistics.median(
                record['reduction_fraction'] for record in subset), 1),
            'max_witness_events': max(record['witness_events'] for record in subset),
        }
    summary = {
        'browser_failure_witnesses': len(records),
        'target_failures_preserved': len(records),
        'one_minimal_witnesses': sum(record['one_minimal'] for record in records),
        'median_original_events': statistics.median(
            record['original_events'] for record in records),
        'median_witness_events': statistics.median(
            record['witness_events'] for record in records),
        'median_reduction_percent': round(100 * statistics.median(
            record['reduction_fraction'] for record in records), 1),
        'mean_reduction_percent': round(100 * statistics.mean(
            record['reduction_fraction'] for record in records), 1),
        'total_predicate_evaluations': sum(
            record['predicate_evaluations'] for record in records),
        'total_predicate_cache_hits': sum(
            record['predicate_cache_hits'] for record in records),
        'failure_kinds': dict(collections.Counter(
            record['target']['kind'] for record in records)),
        'families': groups,
        'wall_seconds': round((time.time_ns() - started) / 1_000_000_000, 3),
        'minimality_scope': ('deletion-1-minimal observed events under one exact '
                             'semantic failure key; values and event order are unchanged'),
    }
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    macros = {
        'WitnessCount': summary['browser_failure_witnesses'],
        'WitnessMedianOriginal': summary['median_original_events'],
        'WitnessMedianReduced': summary['median_witness_events'],
        'WitnessMedianReduction': summary['median_reduction_percent'],
    }
    if args.paper_dir is not None:
        paper = args.paper_dir / 'generated' / 'witnesses'
        paper.mkdir(parents=True, exist_ok=True)
        (paper / 'numbers.tex').write_text('\n'.join(
            f'\\newcommand{{\\{name}}}{{{value}}}' for name, value in macros.items()) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
