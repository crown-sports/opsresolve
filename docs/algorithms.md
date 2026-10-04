# Diagnosis, selection, and verification

## Bounded consistency model

For each declared service, the fault catalog contains endpoint unavailability and
local business failure. Each binding contributes one configuration-drift atom.
The engine enumerates compatible sets of up to `max_faults` atoms (default two,
maximum three), capped at 50,000 worlds.

A required-edge DAG determines each fault's affected service and its ancestors.
An unavailable endpoint predicts its own unreachable business/liveness check and
failed ancestor business checks. Local and configuration failures predict failed
business checks for the affected closure. A configuration probe directly observes
its binding's match or drift. Liveness is assumed independent of business edges.

An observation filters worlds whose predicted result disagrees with the known
outcome. `unknown` removes none. This distinguishes failure to obtain evidence
from evidence of health. A timeout is unknown rather than proof that a process
is down. There must be an actual passing entry business request to report health.

No feasible world means model conflict. Multiple incomparable subset-minimal
worlds mean ambiguity. One minimum world is a conditional explanation, not a
proof that the catalog covers every cause. Directly observed configuration drift
is distinguished from inferred failure propagation. A fault's supporting evidence
is linked when removing that atom changes the observation's prediction.

## Probe selection

Let `W` be the remaining worlds and assign each a cardinality weight
`w(F) = 0.08^|F|`. Normalize those weights within `W`. They are declared modeling
assumptions, not probabilities calibrated on historical production incidents.

For a candidate probe, partition worlds by its deterministic predicted outcome.
Compute the entropy `H = -Σ p(outcome) log2 p(outcome)` and choose the largest
`H / declared_cost` that fits the remaining budget. With deterministic predictions,
this entropy is the expected reduction of model uncertainty for that test.

Selection retains simultaneous-fault worlds even if the current minimum
explanation contains only one fault. Otherwise a discovered gateway error could
prematurely suppress a useful downstream check. The budget accounts for declared
cost units, not measured latency or a hard real-time deadline. Cancellation is
checked between bounded network probes.

Included comparisons use the same evidence adapters and consistency solver:

- `all`: every declared business, liveness, and configuration check, with enough
  budget to complete all checks.
- `fixed`: entry first, then configuration-first static ordering, skipping checks
  whose remaining worlds predict only one result. This is an informed baseline.
- `active`: entropy per declared cost ordering.

These mechanisms use established model-based and active diagnosis ideas. Small
graphs with cheap directly observable settings can make a fixed order as effective
as entropy ranking. The results report that outcome instead of claiming novelty
or universal superiority.

## Intervention

The plan builder requires one minimum explanation and directly observed drift for
every proposed correction. A correction must match a repair-enabled, nonsensitive,
existing JSON field declared hot-reloadable by the owner. Unsupported actions block
automatic repair. Plans contain source evidence IDs, whole-file hashes, exact
before/after values, target intent fingerprint, and five-minute expiry.

The transaction checks all file preconditions before mutation, saves original
bytes and a recovery ledger, and uses same-filesystem atomic replacements. It
preserves file ownership and mode. An intervention may touch multiple files; those
individual replacements are not globally atomic to other readers.

After mutation, every declared business endpoint is checked twice. Recovery is
verified only when all pass. Failed or unknown recovery checks restore original
bytes, provided a file still has the engine's proposed digest. A foreign digest
creates a manual-recovery conflict. SIGKILL recovery uses the durable backup map
and the same comparison rule. File hashes and event links are unsigned integrity
checks, not adversarial authenticity guarantees.

## Trace evidence

The OTLP importer builds parent-child trees by `(trace_id, span_id)`, detects
cycles/conflicting duplicates, and reports missing parents. A failed span with no
recorded failed descendant is an origin candidate. Failed ancestors are labeled
propagation. The failure predicate is explicit OTLP error status or recorded HTTP
status ≥ 400; the latter is an application-oriented analysis predicate, independent
of SDK conventions for client/server status assignment.

Exclusive duration subtracts the union of direct same-service child intervals,
clamped to the parent interval. This avoids double-counting overlapping children.
It does not compensate for all clock skew, distinguish service replicas without
additional metadata, infer CPU time, or reconstruct a distributed critical path.
Sampling and missing instrumentation can hide a deeper cause. Trace results are
an input to an investigation, not authorization to mutate a system.
