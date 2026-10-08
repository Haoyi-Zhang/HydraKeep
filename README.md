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
- `tests/`: 122 unit, finite-model, corruption-rejection, compatibility, and
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
```

In the full project, the parent Makefile runs the analysis/build gates in
dependency order. In the standalone repository, run the commands above directly.
Missing or duplicate schedule
cells, malformed typed bodies, mismatched transaction/consumer links, browser
errors, stale stored verdicts, specification disagreement, and compatibility
drift fail the analysis.

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

The two profiles contain 256 canonical browser runs and 512 receiver records.
Their raw records live in `results/transactions` and
`results/typed-transactions`; `results/witnesses` contains 144 exact-key,
deletion-1-minimal reductions.

## Native and external evidence

`results/native-integration` contains native SSR, build, version, historical,
native-submit, public-form, and direct InitRacer control records.  These studies
require normal loopback document navigation and pinned Node dependencies to
rerun.  The saved records retain their environment data and can be reanalyzed
without reconstructing the original runtime.

## Evidence classes

The package distinguishes browser runs, HTTP receipts, generated model traces,
compatibility reinterpretations, smoke executions, and unavailable cells.  Do
not add model or reinterpretation counts to the browser-run denominator.  Do not
represent authored configurations as independent deployed applications or
controlled faults as newly discovered framework defects.

Node.js 22 or newer is required for source-effect parsing.
Browser reruns additionally require the pinned Playwright and runtime inputs.
