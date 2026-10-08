# Transaction profile: scope fixed before browser outcomes

The retained single-consumption interpreter is unchanged. This separate profile
supports multiple named consumers and overlapping submissions. Its contract is
external to the adapter. A consume event records the start of a submit handler,
not the time a queued request is eventually sent. Each receiver record is matched
by a unique transaction identity. The latest edit at consumption is owed to that
transaction even when another edit, reset, removal, or receipt occurs first.

Each consumer declares a field set and a subset whose display obligations may end
at consumption. Nonterminal saves release no display obligations. Terminally
consuming field a never releases b. A later edit starts a new revision, even after
a terminal consumption. Permitted resets advance only the named field's epoch;
they cannot change frozen earlier transactions. No source-effect proposal changes
this oracle. A completed trace requires one unique matching receipt per consume,
and every final live edit must have been consumed by a matched transaction.

The advance over the retained monitor is the scoped handoff rule, not a claim to
invent transaction IDs, runtime trace slicing, or general concurrency monitoring.
It remains an observational test for a bounded local Web workflow, not a proof
about unobserved browser instructions or arbitrary asynchronous applications.

## Authored browser contrasts

Eight workflows have a paired React/Vue implementation: immutable snapshot;
deferred read of a mutable store; stale closure; acknowledgment that clears a newer
edit; terminal single-field submission; overbroad clearing of another field;
permitted local reset between submissions; and stale second payload after reset.
These are controlled sensitivity/negative controls, not independently discovered
framework defects. Two placements (before/after hydration), two dispatch orders,
and repeated runs are crossed. HTTP records, actual user edits, and intermediate
checkpoints must all agree with the trace. Both correct and wrong outcomes are
reported. No reference outcomes are derived from the adapter's workflow name.

The new runs use offline documents and pinned real framework bundles because the
current managed Chromium prohibits localhost document navigation. Their initial
HTML comes from browser prerender, not a fresh server-renderer invocation. Fetch
requests still reach an actual local HTTP receiver. Retained native-SSR experiments
remain separately identified and reanalyzed, not described as newly rerun.
