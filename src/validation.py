"""Evidence gate for a bounded pair-grid proposal; no browser or case labels."""
from collections import defaultdict
from form_oracle import signature
from multi_explorer import PairSchedule, pair_grid, pair_quotient, representative


def validate_pair_runs(grid, quotient, independence, *, repetitions=2):
    """Reject incomplete grids, stale proposal flags, or diagnostic disagreement.

    `independence` must be recomputed from the current handler source, not taken
    from observed verdicts. This gate establishes recorded bounded agreement,
    not general source-level commutativity or future-execution correctness.
    """
    def index(rows, reps, reduced):
        found = {}
        for row in rows:
            case = row['case']
            if case not in independence:
                raise ValueError('unknown configuration')
            s = PairSchedule(**row['schedule'])
            k = (case, row['rep'], s)
            if k in found:
                raise ValueError('duplicate case/repetition/schedule')
            if row['source_independent'] is not independence[case]:
                raise ValueError('source proposal flag does not match current source')
            found[k] = row
        expected = {(c, r, s) for c, independent in independence.items()
                    for r in range(reps)
                    for s in (pair_quotient(independent) if reduced else pair_grid())}
        if set(found) != expected:
            raise ValueError('missing or unexpected bounded schedule')
        return found

    reference = index(grid, repetitions, False)
    replay = index(quotient, 1, True)
    comparisons = 0
    for (case, rep, s), row in reference.items():
        if signature(row['oracle']) != signature(reference[(case, 0, s)]['oracle']):
            raise ValueError('repeated reference signature disagreement')
        target = representative(s, independence[case])
        if signature(row['oracle']) != signature(reference[(case, rep, target)]['oracle']):
            raise ValueError('within-class signature disagreement')
        if rep == 0 and target != s:
            comparisons += 1
    for (case, rep, s), row in replay.items():
        if signature(row['oracle']) != signature(reference[(case, 0, s)]['oracle']):
            raise ValueError('separate representative replay disagreement')
    return {'reference_runs': len(reference), 'representative_runs': len(replay),
            'omitted_comparisons': comparisons, 'accepted': True}
