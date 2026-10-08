"""Obligation-preserving counterexample slicing for transaction traces.

This is a domain predicate over ordinary deletion-based minimization. A
candidate is accepted only when (1) the incremental monitor and independent
prefix specification agree, (2) the candidate remains conclusive, and (3) the
same field/phase/epoch/revision/transaction failure is present. Event payloads
are never rewritten and relative order is preserved.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil
from typing import Any, Iterable

from transaction_oracle import diagnosis, interpret_transactions
from transaction_spec import specify

FailureKey = tuple[str, str, str, int, int, str]


def failure_key(failure: dict[str, Any]) -> FailureKey:
    return (str(failure.get('field')), str(failure.get('kind')),
            str(failure.get('phase')), int(failure.get('epoch', 0)),
            int(failure.get('revision', 0)), str(failure.get('transaction')))


def failure_keys(result: dict[str, Any]) -> set[FailureKey]:
    return {failure_key(item) for item in result.get('failures', [])}


@dataclass(frozen=True)
class SliceResult:
    indices: tuple[int, ...]
    events: tuple[dict[str, Any], ...]
    target: FailureKey
    predicate_evaluations: int
    predicate_cache_hits: int
    one_minimal: bool


class ObligationWitness:
    """Minimize one observed failure while retaining semantic evidence."""

    def __init__(self, contract: dict[str, Any], target: FailureKey, *, memoize: bool = True):
        self.contract = contract
        self.target = target
        self.evaluations = 0
        self.memoize = memoize
        self.cache_hits = 0

    def preserves(self, trace: Iterable[dict[str, Any]]) -> bool:
        self.evaluations += 1
        candidate = list(trace)
        try:
            monitor = interpret_transactions(candidate, self.contract)
            specification = specify(candidate, self.contract)
        except (KeyError, TypeError, ValueError, IndexError):
            return False
        return (monitor['status'] == 'violation'
                and not monitor.get('unknown')
                and diagnosis(monitor) == diagnosis(specification)
                and self.target in failure_keys(monitor))

    def minimize(self, trace: list[dict[str, Any]]) -> SliceResult:
        indexed = list(enumerate(trace))
        # This cache exists for one immutable observed trace and one fixed
        # contract/target only. Original indices preserve duplicates and order.
        memo: dict[tuple[int, ...], bool] = {}
        self.evaluations = 0
        self.cache_hits = 0
        def accepted(rows):
            key = tuple(index for index, _ in rows)
            if self.memoize and key in memo:
                self.cache_hits += 1
                return memo[key]
            result = self.preserves(event for _, event in rows)
            if self.memoize:
                memo[key] = result
            return result
        if not accepted(indexed):
            raise ValueError('Original trace does not preserve the requested failure')

        # Classical partition-based deletion, with a semantic predicate.
        granularity = 2
        while len(indexed) >= 2:
            width = ceil(len(indexed) / granularity)
            reduced = False
            for start in range(0, len(indexed), width):
                candidate = indexed[:start] + indexed[start + width:]
                if candidate and accepted(candidate):
                    indexed = candidate
                    granularity = max(2, granularity - 1)
                    reduced = True
                    break
            if reduced:
                continue
            if granularity >= len(indexed):
                break
            granularity = min(len(indexed), granularity * 2)

        # Deterministic deletion-1 fixed point. This also makes the advertised
        # minimality independent of partition boundaries.
        changed = True
        while changed:
            changed = False
            for position in range(len(indexed)):
                candidate = indexed[:position] + indexed[position + 1:]
                if candidate and accepted(candidate):
                    indexed = candidate
                    changed = True
                    break

        one_minimal = all(
            not candidate or not accepted(candidate)
            for position in range(len(indexed))
            for candidate in [indexed[:position] + indexed[position + 1:]])
        if not one_minimal:
            raise AssertionError('Counterexample is not deletion-1-minimal')
        return SliceResult(
            indices=tuple(index for index, _ in indexed),
            events=tuple(event for _, event in indexed),
            target=self.target,
            predicate_evaluations=self.evaluations,
            predicate_cache_hits=self.cache_hits,
            one_minimal=True,
        )
