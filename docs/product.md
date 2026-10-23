# Reading a diagnosis and a trace comparison

## Recovery means the business request works

A green health endpoint can coexist with a broken checkout. The storefront demo
checks the request users make, repairs the gateway's upstream URL, then discovers
the catalog's database fault. Each proposed patch includes its original value
and file hash. Applying a stale plan fails; an unsuccessful recovery check
triggers rollback. [Recovery tests](../tests/test_live_recovery.py).

Keep the target manifest close to the service configuration. It tells the tool
which dependencies, probes and JSON fields it may use. A URL alone gives endpoint
triage; it does not discover hidden services or authorize repairs.
[Target setup and repair contracts](usage.md).

## Read trace comparisons as a change in the sample

`trace-compare` groups spans by service and operation name. Defaults require
five spans on each side. A latency regression must exceed **both 20% and 10 ms**;
any increase in error rate also fails. Missing or undersampled operations are
reported separately and fail `--check` rather than disappearing from the report.
Run `opsresolve trace-compare --help` to adjust thresholds.

The bundled sample changes p95 from **100 to 180 ms** and errors from **0% to 10%**.
Its nonzero exit is expected. Use exports with comparable traffic and sampling;
a comparison shows a recorded change, not its cause or statistical significance.
[Comparison tests](../tests/test_trace_compare.py).

## Inspect the implementation

- [Diagnosis](algorithms.md): preserve multiple fault candidates and select probes.
- [Experiments](results.md): topology fixtures, model comparisons and failures.
- [Interruption handling](../tests/test_interruption.py): stop safely during repair.

The commands work in v0.2.0. This guide and the shorter README are maintained on main.
