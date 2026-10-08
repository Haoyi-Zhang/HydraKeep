# Scoped consumption semantics and proof obligations

## Domain and trust boundary

The trace is finite and totally ordered. An observation supplies uniquely resolved
logical field identifiers, scalar values, and the completed requested value for a
trusted, available user edit. User-event provenance and receiver fidelity are
observer premises; the monitor does not prove the browser adapter honest. The
HTTP evidence gate checks request bodies against receipt events and recorded
transaction correspondence. Missing/duplicate identities or receipts are not clean.

A field has an epoch e (number of permitted reset/removal transitions), a revision
r (number of accepted edits), and a most recent expected value v. A consumer c
specifies a field scope S_c and a display-release subset L_c contained in S_c.
Each consumption has a distinct transaction identity t. Nonterminal consumers set
L_c empty. The special case S_c = L_c = all fields, one consumption, and no later
edit recovers the retained terminal profile. Legacy records and their interpreter
are retained unchanged, including legacy receipt-without-consume behavior.

## Prefix definition

For a field f and prefix p, j_f is the last accepted edit position. d_f is the last
permitted reset/removal position. l_f is the last consumption position for which
f belongs to that consumer's L_c. A nonexistent position is -1. Its display
obligation is active exactly when j_f > max(d_f, l_f), with value v_f from j_f.
An edit does not advance e; each applicable reset/removal does. A new edit can
reactivate a field after consumption without altering any earlier pending request.

At consume(t,c), before applying its release, copy the prefix obligation for all
f in S_c into B[t,f] = (active, e, r, v, removed, visible). These copies are immutable.
At receipt(t,c,payload), compare the payload entry only with B[t,f], not with the
latest field state. An active entry must be present and type-equal; a removed-field
entry must be absent. Live obligations for unrelated fields remain checked. Reset
or receipt processing never deletes an already observed failure.

Closing a run requires a unique matching receipt for each consumption and every
final live (f,e,r) token to have occurred in a receipted consumption. This last
condition does not reject an explicitly discharged edit or demand submission after
a permitted reset. It prevents silently calling a newer, never-consumed edit clean.
It is an experiment-completion requirement, not a claim that users must submit all
forms. No arbitrary eventual-delivery timeout is encoded as functional data loss.

## Invariant argument

Assume well-formed observations. Initially there is no j_f and no active obligation.
An accepted edit updates only that field's j_f, v_f and r_f. The new position exceeds
all preceding d_f and l_f, so it activates exactly that field. A permitted reset or
removal sets d_f to the current position and deactivates only its permitted fields.
At consumption, copying the pre-event state captures precisely the obligation
before l_f changes. Applying the declared release sets l_f only for fields in L_c;
the active condition is thereby false for those fields and unchanged for others.
A receipt changes none of j_f, d_f or l_f. Induction proves equivalence of the
incremental live state with the prefix definition. Since B[t,f] is copied once and
never mutated, every receipt comparison uses its originating consumption prefix.
The comparison operations record exactly the discrepancies under these invariants
at the supplied checkpoints, and the failure set is monotone.

This is a proof of the specified monitor rules, not a proof that arbitrary program
execution is fully observed. The executable slow specification recomputes prefix
indices and matches receipts by searching for their origin. It shares no state-update
code with the incremental monitor. Tests compare complete diagnostic signatures on
1,152 well-formed generated traces, alongside separate protocol-rejection tests.

## Two separations

1. Transaction identity cannot be replaced with current value. Consider
   edit(a,u); consume(t1); edit(a,v); consume(t2); receipt(t2,v); receipt(t1,u), u != v.
   Both receipts are correct. Comparing t1 with current v creates a false alarm.
   Replacing the last payload with v creates the opposite error: a latest-value
   checker accepts a response that violates the t1 obligation.
2. Consuming one field cannot release another field. After edits to a and b,
   consume(t1,onlyA) with L_onlyA={a} permits removal of a. Overwriting b before its
   own next accepted edit still violates b. A global terminal flag misses this
   prefix failure even when a later edit repairs b and both final receipts look
   correct. The scoped-submit/overbroad-clear browser pair exercises this case.

## When acknowledgment orders commute

For fixed immutable payloads, matched transaction IDs, identical field observations,
and acknowledgments with no application effects, receipt checks commute as a set
of per-transaction comparisons and coverage tokens. This does not justify pruning
application acknowledgment orders: callbacks can mutate live fields, update owners,
or remove nodes. The transaction experiment therefore retains both dispatch orders;
it does not transfer the old handler-only source quotient to asynchronous callbacks.
The ack-clear contrast illustrates why application effects must be included.

## Cost

For F declared fields, K consumptions, and N observations, the implementation visits
O(N F + sum_t |S_t|) field records, excluding diagnostic deduplication and parsing.
It retains O(F + sum_t |S_t|) obligation state until the bounded experiment ends.
The current list-based diagnostic deduplication adds up to quadratic cost in the
number of distinct discrepancies; no constant-time or industrial-scale throughput
claim is made. The proof concerns rules, not a performance optimality result.

Parametric indexing and trace slicing are established runtime-verification ideas;
see Rosu and Chen, LMCS 8(1:9), 2012. The specialization here is the Web-field
obligation, consumption-time value, scope-specific display release, and their
receiver-backed interpretation across a hydration handoff.
