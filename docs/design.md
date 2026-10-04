# OpsResolve development contract

## Problem and audience

Small teams can see an HTTP 502/503 but often cannot tell whether the application,
a dependency, or a persisted routing setting caused it. Restarting a process does
not correct a persisted setting. One visible failure can conceal a second fault.

OpsResolve is a local incident workbench for application owners. Input is a failing
URL or a small target manifest describing service endpoints, dependencies, and
optional JSON configuration contracts. Output is a live investigation, competing
explanations, exact configuration changes, and an independently checked recovery.

## Product boundaries

The first release supports HTTP GET business checks, separate liveness checks,
JSON configuration contracts, and bounded local configuration repairs. A URL alone
supports endpoint triage; a manifest enables dependency diagnosis and repair. It
does not discover arbitrary infrastructure, repair arbitrary source code, or
control a production Kubernetes cluster. These boundaries appear in the UI and
quickstart. A model is optional: investigation and repair verification work on CPU.

## Algorithms and their assumptions

1. Enumerate bounded fault sets over endpoint unavailability, local application
   failure, and configuration drift. Predict business-check failure propagation
   through the declared dependency DAG. Filter sets against actual observations.
2. Choose the next available probe using entropy of its predicted outcomes divided
   by the operator's declared cost. This is established active diagnosis, not a
   new information-theoretic algorithm. Weights are model assumptions, not
   calibrated production probabilities. Keep multi-fault worlds while selecting
   probes so a visible fault does not suppress checks for concealed faults.
3. Return subset-minimal consistent explanations and unresolved alternatives. An
   empty feasible set is a model conflict, not an invented root cause. Unknown
   probes contribute no false negative evidence.
4. Build changes only from directly observed, repair-enabled configuration drift.
   Require current file hashes and exact field preconditions. Validate all business
   endpoints twice after a transaction; roll back byte-for-byte on failed recovery.
   A minimum model explanation is provisional until intervention succeeds.

The propagation model assumes that each declared dependency is required for the
declared business check. Optional/fallback dependencies and intermittent failures
require a different model. Liveness must bypass business dependencies. Cardinality,
budget, unknown checks, and model conflict must be visible to operators.

## Architecture

Domain values and graph/diagnosis algorithms are independent of adapters. Typed
probe strategies implement HTTP and JSON checks. A workflow coordinates a budget,
an event journal, and cancellation. A repair transaction owns preconditions,
atomic writes, validation, and rollback. Thin CLI and HTTP controllers share the
same workflow. An optional model explains the deterministic investigation, with
structured fault identifiers and exact evidence references checked before display.

The UI exposes target setup, a dependency map, investigation timeline, diagnosis,
configuration diffs, recovery checks, and downloadable incident reports. The lab
starts real isolated HTTP service processes backed by SQLite; it is not a drawn
animation. Only owned lab configurations are writable in the default web server.

## Development order and acceptance criteria

1. Core: strict manifest validation; dependency model; multi-fault inference;
   cost-aware probe selection; meaningful unknown/ambiguous/conflict results.
2. Execution: real HTTP and configuration checks; cancellable workflow; persistent
   incident history; precise report export.
3. Recovery: bounded patch plans; stale-plan refusal; failed-recovery rollback;
   verification across every declared service, including hidden faults.
4. Product: usable browser workbench and CLI; single-command real fault lab;
   real-target setup documentation; no API key needed for the first successful use.
5. Evidence: paired experiments against full and fixed-order checks, single and
   multiple actual faults, fresh topologies, actual before/after recovery; local
   5090 model report evaluation; publish failures and exact source provenance.
6. Release: independent installation smoke test, browser QA, Linux tests, secret
   scan, public MIT repository and prerelease with a real demo screenshot.

## Validation discipline

Truth labels stay in the experiment harness, outside manifests, observations,
planner inputs, and model prompts. Development fixtures are not an external
production benchmark. Cost units and measured duration are separate quantities.
Compare algorithms with the same checks, observations, and diagnosis solver.
Record unsuccessful recovery and rejected model reports, including denominators.
Do not assert that OpenClaw, Hermes, OpenHands, or existing SRE agents cannot be
configured to perform these tasks. The value is an accessible integrated workflow
with bounded executable diagnosis and verifiable recovery.

## Implemented acceptance evidence

The core, adapters, transactional recovery, browser workbench, trace import,
and optional local-model explanation are implemented. The UI was exercised
against actual owned service processes through exact patch review and ten
passing recovery requests; the screenshots in `docs/assets` show that result.
Real-target URL setup and a complete dependency/configuration manifest are
documented in [the usage guide](usage.md).

[The published measurements](results.md) cover 44 live-process incidents on
three topologies, paired full/fixed/active policies, 29 verified configuration
recoveries, 290 post-change business checks, and nine actual restart-only
comparisons. A single RTX 5090 generated 18 optional explanations; all five
rejected outputs are retained. The 47-test local/Linux suite includes a real
SIGKILL interruption and guarded transaction recovery.

The active policy does not outperform the informed fixed-order policy on these
fixtures. That finding narrows the algorithm claim rather than changing the
reported denominator. The next evidence milestone is an independently selected
external application with declared required dependencies and known injected
faults. Kubernetes adapters, unknown-topology discovery, and production-grade
multi-operator access remain future work, not release features.
