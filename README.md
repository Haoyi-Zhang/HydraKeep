# HydraKeep artifact

This directory contains the executable implementation, fixtures, canonical
measurements, analysis, and tests for HydraKeep.  The artifact follows accepted
form edits from trusted browser actions through framework state and named
consumer transactions to actual loopback receiver payloads.

## Layout

- `src/`: incremental form and transaction interpreters, independent prefix
  specifications, browser adapters, source effects, native integrations, and
  semantic-witness code;
- `fixtures/`: authored contracts/workflows, native cases, semantic controls,
  and the licensed external Next.js example with provenance;
- `scripts/`: browser execution, isolated typed-matrix orchestration, analysis,
  compatibility checking, source recovery, figure generation, and paper audit;
- `tests/`: unit, finite-model, corruption-rejection, compatibility, and
  witness-minimality tests;
- `results/`: canonical raw browser/receiver records, summaries, environments,
  generated model checks, witnesses, and structural audits;
- `vendor/` and `licenses/`: pinned browser-side runtime/parser inputs and their
  redistribution notices.  No browser executable or installed dependency tree
  is included.

## Core checks

```sh
python -m unittest discover -s tests -v
python scripts/analyze.py
python scripts/analyze_phase_grid.py
python scripts/analyze_native_integration.py
python scripts/analyze_transactions.py
python scripts/analyze_typed_transactions.py
python scripts/minimize_witnesses.py
python scripts/check_profile_compatibility.py
python scripts/scheduling_amortization.py
```

In the full project, the parent Makefile runs the analysis/build gates in
dependency order. In the standalone repository, run the commands above directly.
Missing or duplicate schedule
cells, malformed typed bodies, mismatched transaction/consumer links, browser
errors, stale stored verdicts, specification disagreement, and compatibility
drift fail the analysis.

Browser transaction rows first pass `src/evidence_admission.py`. Each completion
must cite a fresh trusted native event from its own action-start record, with the
same logical field, physical node and typed value. Consumption must precede
dispatch, acknowledgment and receipt for each transaction. Physical-node IDs
must be positive integers; repeated Boolean, float or string values do not become
valid node identities by matching each other. Evidence rejection
raises an error; it is not a preservation verdict. The incremental and prefix
interpreters remain conditional semantic models and are not provenance validators.

## Transaction profiles

`fixtures/transactions` contains the two-text profile.  It exercises immutable
snapshots, deferred mutable reads, stale closures, late acknowledgment clearing,
field-scoped terminal submission, overbroad clearing, permitted reset followed
by a new edit, and stale post-reset payloads.

`fixtures/typed-transactions` contains the heterogeneous profile.  It adds text,
Boolean checkbox, single-select, type-sensitive payloads, and physical-node
replacement under stable logical identity.  `scripts/run_typed_matrix.py`
executes each configuration and repetition in a separate Chromium process.  A
shard is committed only after exactly four schedule cells, eight receipts,
repeat-stable diagnoses, and independent-prefix agreement are present.

The current two profiles contain 256 canonical browser runs and 512 receiver records,
collected with Chromium 155.0.8059.39 and Playwright 1.57.0.
Their raw records live in `results/transactions` and
`results/typed-transactions`; `results/witnesses` contains 144 exact-key,
deletion-1-minimal, admission-preserving reductions (median 41 to 18 events).
The existing `shards/` files are older saved executions, not the source of this
current combined matrix. `run_typed_matrix.py --reuse` must not be used to admit
those older records: rerun shards with the current observer and gate instead.

## Native and external evidence

`results/native-integration` contains native SSR, build, version, historical,
native-submit, public-form, and direct InitRacer control records.  These studies
require normal loopback document navigation and pinned Node dependencies to
rerun. The native HTML POST file has been regenerated: 56 current action-bound
native-SSR/native-submission executions retain actual URL-encoded receiver bodies.
Other native/version/historical/public records retain the older observer evidence;
receiver and semantic reanalysis does not upgrade their action provenance.

```sh
python scripts/run_transactions.py
python scripts/run_typed_transactions.py
python scripts/run_native.py --study native-submit --repeats 1
python scripts/compare_playwright_assertions.py
```

The last command performs a separate 48-run same-execution comparison on snapshot,
late-read and stale-closure two-text workflows. Ordinary live-value and immutable
receiver-snapshot assertions agree with the monitor on 16 clean and 32 violating
runs; this is not a reset/removal or throughput comparison.

The 608-to-482 schedule reduction excludes validation. Counting one full setup
validation, the first schedule-count saving occurs at five representative rounds;
with the retained offline study's two setup validations, at ten. The current
runner has no persistent automatically invalidated quotient cache. Any framework,
binding, handler, consumer, contract, observer or bounded-profile change requires
renewed full-grid validation. No amortized deployment wall-time benefit is measured.

## Evidence classes

The package distinguishes browser runs, HTTP receipts, generated model traces,
compatibility reinterpretations, smoke executions, and unavailable cells.  Do
not add model or reinterpretation counts to the browser-run denominator.  Do not
represent authored configurations as independent deployed applications or
controlled faults as newly discovered framework defects.

Node.js 22 or newer is required for source-effect parsing.
Browser reruns additionally require the pinned Playwright and runtime inputs.
