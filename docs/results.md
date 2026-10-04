# Measured results — 2026-10-04

This release was exercised against real local HTTP processes, SQLite operations,
and actual configuration writes. The fixtures belong to this project; these
results are not a production success rate, a held-out fault-family evaluation,
or a comparison with other agent products.

## What ran

The experiment creates five-service fanout, chain, and diamond applications with
opaque service identifiers and fresh runtime ports. Seed `90421` selects the
instances. Across the three topologies there are **44 incidents**: three healthy
cases, 29 configuration incidents, and 12 application/unavailable-process
incidents. Configuration incidents include wrong route paths, wrong route ports,
wrong database paths, and twelve simultaneous fault pairs: four per topology.

The fault labels stay in the experiment harness. Neither the target manifest,
probe implementation, diagnosis solver, repair planner, nor model prompt receives
the injected truth labels. Each case is investigated with the same available
probes and solver under three policies before any repair is applied:

- **Full checks:** run every declared business, liveness, and configuration check.
- **Fixed order:** use an informed configuration-first order; skip checks that no
  longer discriminate compatible fault sets.
- **Active:** choose the next discriminating check by predicted outcome entropy
  divided by declared cost, retaining compatible multi-fault possibilities.

The full-check policy receives the cost of all checks as its budget. Fixed and
active policies each receive eight cost units. Cost is declared effort, not
elapsed seconds or tokens. The three graph shapes and fault families are also
used in development tests; fresh identifiers do not make them unseen families.

## Diagnosis and investigation cost

| Policy | Exact explanations | Mean declared cost | Mean checks | Budget violations |
|---|---:|---:|---:|---:|
| Full checks | 44/44 | 11.4205 | 15.6818 | 0 |
| Informed fixed order | 44/44 | 4.4318 | 8.0455 | 0 |
| Active selection | 44/44 | 4.4375 | 8.1364 | 0 |

“Exact” means the returned explanation list contains exactly the injected fault
set, including the empty healthy set. It does not mean arbitrary production
causes can be inferred from these observations.

Active selection used **61.14% less declared cost** and **48.12% fewer checks**
than checking everything. **It did not beat the informed fixed-order baseline**;
that baseline was slightly cheaper on these fixtures. The experiment supports
bounded adaptive investigation and hidden-fault coverage, not a general claim
that entropy selection outperforms good operational heuristics.

The complete suite was run independently on macOS ARM64/Python 3.12.12 and
Linux x86-64/Python 3.12.14. Both produced the same diagnosis, cost, and recovery
counts. Median investigation durations were:

| Host | Full checks | Fixed order | Active selection |
|---|---:|---:|---:|
| macOS development machine | 99.23 ms | 57.37 ms | 49.98 ms |
| Linux evaluation host | 2450.72 ms | 1482.05 ms | 1488.18 ms |

These durations include journal persistence and actual requests. The hosts have
different storage, process, and load conditions; model startup overlapped part
of the Linux run. They are observations, not controlled cross-host speed claims.

## Recovery that actually happened

All **29 repairable incidents** received actual configuration changes and
**29/29 recovered**. Each recovery ran two rounds of business checks against all
five services: **290/290 passing post-change requests**. The 12 manual incidents
did not receive automatic patches; the three healthy incidents needed no repair.

In nine additional paired checks, the same persisted configuration faults were
re-injected and the owned service processes were actually restarted. **All nine
entry endpoints still returned HTTP 503.** This demonstrates the particular
problem the configuration recovery workflow addresses: restarting these
processes does not correct their saved route or database settings.

The test suite covers refusal of stale plans and changed target intent,
failed-recovery rollback, and a foreign configuration write during validation.
It also launches a real repair process, sends **SIGKILL after its first atomic
configuration write**, and then restores original bytes through the durable
transaction ledger. **47 tests passed on both local and Linux environments.**
Per-file atomic replacement and this process-interruption test do not establish
global multi-file atomicity or comprehensive power-loss guarantees.

## Optional RTX 5090 model explanation

The core workflow does not require a model or GPU. The optional explanation
adapter was evaluated on one NVIDIA GeForce RTX 5090 using
`Qwen/Qwen3-4B-Instruct-2507`, pinned revision
`cdbee75f17c01a7cc42f958dc650907174af0554`. Torch was `2.8.0+cu128` and
Transformers `4.57.6`; inference used BF16, SDPA, greedy decoding, and up to 900
new tokens. The available host has eight GPUs; only GPU index zero was used.

The model was given **18 already-computed diagnoses** selected deterministically
from the captured active-policy records. **13 explanations were accepted and
five were rejected** by structured fault-identifier and exact-quotation checks.
Median request duration was 4023.99 ms.

| Rejected case | Reason |
|---|---|
| fanout-07 | Quotation did not occur exactly in captured evidence |
| chain-07 | Quotation did not occur exactly in captured evidence |
| chain-09 | Quotation did not occur exactly in captured evidence |
| diamond-02 | Invented or duplicated diagnosed fault identifier |
| diamond-08 | Invented or duplicated diagnosed fault identifier |

Acceptance is not a measurement of semantic truth or model-only root-cause
accuracy. These rejected outputs remain in the published records. The model has
no authority to select checks, write configuration, or declare recovery.

## Trace demonstration

[The example export](../examples/trace-export.json) contains actual HTTP and
SQLite span timings from the owned fault lab. It includes a catalog database
failure and its propagated upstream failures. `opsresolve trace` identifies the
deepest recorded error operations, lists service-call edges, and computes
exclusive span duration by subtracting the union of same-service child intervals.
It analyzes recorded origin candidates; no production trace accuracy benchmark
is claimed. The browser was exercised through diagnosis, exact patch review,
verified recovery, trace analysis, and Chinese/English rendering.

## Provenance and raw evidence

All reported source runs use SHA-256:

```text
b5254bca0417b92cb137226da5a3662e33d572567f98cc57549e9b386bb0469c
```

`benchmarks/run.py::source_digest` hashes sorted repository-relative paths and
bytes for Python core modules, browser JavaScript/CSS/HTML, and both benchmark
scripts. Documentation, tests, build metadata, and result files are excluded.

- [macOS aggregate](results/2026-10-04/local-report.json) and
  [all 132 policy rows](results/2026-10-04/local-rows.jsonl).
- [Linux aggregate](results/2026-10-04/linux-report.json),
  [all 132 policy rows](results/2026-10-04/linux-rows.jsonl), and
  [complete investigations, plans, and active recovery records](results/2026-10-04/linux-records.jsonl).
- [Model aggregate](results/2026-10-04/model-report.json) and
  [all 18 prompts and outputs, including failures](results/2026-10-04/model-rows.jsonl).
- [Pinned model file sizes and official hashes](results/2026-10-04/model-manifest.json),
  [Linux environment](results/2026-10-04/linux-environment.json), and
  [installed package versions](results/2026-10-04/linux-requirements.txt).

Runtime URLs in these public files are loopback addresses from isolated lab
instances. Original service workspaces and their dynamically allocated ports
are no longer live. Recorded evidence is retained for inspection, not replayed
as a fabricated new measurement.

## Reproduce

From a new checkout on Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[web,dev]'
pytest -q
python benchmarks/run.py --seed 90421 --budget 8 --output benchmark-runs/my-run
python -c 'import sys; sys.path.insert(0,"benchmarks"); from run import source_digest; print(source_digest())'
```

Output directories must not already exist. Each run creates and cleans up only
its own service processes and temporary configuration workspace. Incident
records persist under the requested output directory. To repeat the optional
model experiment, install `.[web,model]`, obtain the pinned official weights,
and use the local model adapter:

```bash
opsresolve model-serve --path /path/to/Qwen3-4B-Instruct-2507 --port 8766
# In a second terminal with the same environment:
python benchmarks/model_eval.py \
  --records benchmark-runs/my-run/records.jsonl \
  --output benchmark-runs/my-model-run \
  --endpoint http://127.0.0.1:8766 \
  --model Qwen3-4B-Instruct-2507 --limit 18
```

Dependency ranges allow newer versions; the environment files document this
specific run. GPU kernels, dependency versions, and machine conditions can alter
model wording, acceptance, and latency. The release does not claim deterministic
model output across all hosts.
