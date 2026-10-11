"""Schedule-count accounting, not a wall-time speedup experiment."""
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def account(reference, representatives, validation_repeats, rounds):
    return dict(rounds=rounds, full_grid=reference*rounds,
                validation_plus_replay=reference*validation_repeats + representatives*rounds)


def main():
    summary = json.loads((ROOT / 'results/phase-grid/summary.json').read_text())
    reference, representatives = summary['multi_reference_runs'], summary['multi_quotient_runs']
    rows = {}
    for repeats in (1, 2):
        break_even = math.floor(reference*repeats / (reference-representatives)) + 1
        rows[str(repeats)] = dict(full_reference_validation_repetitions=repeats,
                                first_strictly_cheaper_round=break_even,
                                rounds=[account(reference,representatives,repeats,r)
                                        for r in (1,4,5,10,20)])
    result = dict(reference=reference, representatives=representatives,
                  per_replay_saved_schedules=reference-representatives,
                  marginal_reduction_percent=100*(reference-representatives)/reference,
                  accounting=rows,
                  round_definition='number of representative regression rounds, including initial separate representative validation',
                  invalidation='framework, binding, handler, consumer, contract, observer or bounded-profile change requires renewed reference validation',
                  implementation_limit='runner reruns its reference; no persistent automatically invalidated quotient cache or measured deployment reuse lifetime',
                  cost_limit='schedule counts only; no amortized wall-time result')
    (ROOT / 'results/phase-grid/amortization.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
