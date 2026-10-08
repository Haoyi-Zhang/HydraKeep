# Phase-grid design freeze

## Semantic unit

A configuration declares logical fields independently of its framework code.
Each field has a typed initial value, readiness policy, owner, permitted
transitions, and named consumer.  Browser observations record current properties,
not only HTML attributes.  Legitimate node replacement preserves logical field
identity when the contract and observation layer can establish it; ambiguity is
reported rather than guessed.

## Schedule language

The bounded schedule grid separates edit placement, hydration release, first
state commit, later transition, field order, and receipt order.  Source effects
from the supported handler subset can propose equivalence classes, but they do
not decide correctness.  Unknown or dynamically aliased effects retain the
complete grid.  Every accepted class must agree on the full diagnostic signature
and has an independently executed representative.

## Oracle separation

Contracts are stored apart from workflows and outcomes.  The incremental
interpreter and prefix specification are separately implemented.  Analysis
rejects incomplete cells, browser errors, duplicate identities or receipts,
wrong receiver channels, untrusted edits, and disagreement between the two
interpreters.  A clean result requires observed coverage of the current accepted
revision or a declared field-local discharge.

## Evaluation units

A browser run, HTTP receiver record, schedule cell, framework configuration,
workflow design, model trace, and reinterpretation are different units.  Repeated
runs measure stability; they are not independent applications.  Seeded faults
measure controlled detection sensitivity and are not upstream bug discoveries.
