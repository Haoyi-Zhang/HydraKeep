"""Measure call-local memoization on the retained browser failures."""
from __future__ import annotations
import argparse
import json
import pathlib
import platform
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from witness import ObligationWitness, failure_key
from transaction_oracle import diagnosis, interpret_transactions
from transaction_spec import specify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    inputs = []
    for family, rows, contracts_file in [
        ('transactions', 'results/transactions/transactions.jsonl', 'fixtures/transactions/contracts.json'),
        ('typed-transactions', 'results/typed-transactions/runs.jsonl', 'fixtures/typed-transactions/contracts.json'),
    ]:
        contracts = json.loads((ROOT / contracts_file).read_text())
        for line in (ROOT / rows).read_text().splitlines():
            row = json.loads(line)
            if row['oracle']['status'] == 'violation':
                inputs.append((family, row, contracts[row['case']]))
    records = []
    times = {True: [], False: []}
    for repetition in range(args.repeats):
        per_mode = {}
        # Alternate order to avoid systematically favouring the second pass.
        for mode in ([False, True] if repetition % 2 == 0 else [True, False]):
            start = time.perf_counter_ns()
            results = []
            for family, row, contract in inputs:
                target = failure_key(row['oracle']['failures'][0])
                result = ObligationWitness(contract, target, memoize=mode).minimize(row['trace'])
                monitor = interpret_transactions(list(result.events), contract)
                assert diagnosis(monitor) == diagnosis(specify(list(result.events), contract))
                assert result.one_minimal and target in {failure_key(x) for x in monitor['failures']}
                results.append(result)
            times[mode].append((time.perf_counter_ns() - start) / 1e6)
            per_mode[mode] = results
        for i, (cached, direct) in enumerate(zip(per_mode[True], per_mode[False], strict=True)):
            assert cached.indices == direct.indices and cached.events == direct.events
            if repetition == 0:
                family, row, _ = inputs[i]
                records.append(dict(family=family, run=row['run'],
                                    original_events=len(row['trace']), witness_events=len(cached.events),
                                    cached_evaluations=cached.predicate_evaluations,
                                    direct_evaluations=direct.predicate_evaluations,
                                    cache_hits=cached.predicate_cache_hits))
    direct = sum(x['direct_evaluations'] for x in records)
    cached = sum(x['cached_evaluations'] for x in records)
    output = dict(environment=dict(python=sys.version, platform=platform.platform(), processor=platform.processor()),
                  witnesses=len(records), repetitions=args.repeats,
                  identical_witnesses=True, one_minimal=True,
                  direct_predicate_evaluations=direct, cached_predicate_evaluations=cached,
                  avoided_evaluations=direct-cached,
                  avoided_percent=round(100 * (direct-cached) / direct, 2),
                  elapsed_ms={str(mode): values for mode, values in times.items()},
                  median_ms={str(mode): statistics.median(values) for mode, values in times.items()},
                  records=records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({key: value for key, value in output.items() if key != 'records'}, indent=2))


if __name__ == '__main__':
    main()
