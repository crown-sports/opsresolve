# OpsResolve

Find the configuration behind an HTTP failure, review the changes, and check that business requests recover.

[中文](README.zh-CN.md) · [Setup](docs/usage.md) · [v0.2.1 prerelease](https://github.com/crown-sports/opsresolve/releases/tag/v0.2.1)

![Storefront demo after two configuration fixes: HTTP 200 and ten successful recovery checks](docs/assets/workbench.jpg)

*Local storefront demo: two configuration faults fixed, five services checked twice. The screenshot uses demo data.*

A storefront returns 503 even though its health endpoints are green. The gateway
has the wrong upstream URL; behind it, the catalog has the wrong database path.
OpsResolve finds both, shows the exact field changes, and keeps the checks and
recovery result in an incident report.

## Try the recovery demo

Python 3.11+ on Linux or macOS. No service account or model is needed.

```sh
git clone --branch v0.2.1 https://github.com/crown-sports/opsresolve.git
cd opsresolve
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[web]'
opsresolve serve --demo
```

Open **http://127.0.0.1:8765**. Click **Investigate**, review **Exact changes**,
then **Apply plan & verify recovery**. You should see **HTTP 200** and **10/10**
recovery checks. The demo runs real local HTTP processes and SQLite queries.

Prefer a terminal? `opsresolve demo --report recovery.md` runs the same recovery,
prints `Recovery: verified (10 business checks)`, and stops the temporary services.

## Use your own service or traces

| What you have | What to do | What you get |
| --- | --- | --- |
| One HTTP endpoint | `opsresolve init --url http://127.0.0.1:3000/ --output target.json`, then `opsresolve diagnose target.json --report incident.md` | HTTP observations and endpoint triage |
| A service/dependency manifest | `opsresolve serve --target target.json` | Candidate causes, checks and a report |
| An OTLP JSON export | `opsresolve trace traces.json --output trace-report.md` | Recorded failure origins, propagation and span timing |

Start with a development service or a saved export. A URL does not reveal its
hidden dependencies; add those to the [target manifest](docs/usage.md) when needed.
Repair is opt-in and supports declared, existing JSON fields that the application
can reload. Each patch checks its original values and file hashes, keeps a backup,
and rolls back if the recovery checks fail.

## Compare traffic before and after a change

```sh
opsresolve trace-compare examples/trace-regression/before.json examples/trace-regression/after.json --check
```

The sample deliberately exits **1**: p95 rises from **100 to 180 ms**, and errors
from **0% to 10%**. Replace the paths with your exports; add `--format json
--output comparison.json` for a machine-readable report. Operations are matched
by service and name. Missing or undersampled operations also fail the gate.

Defaults are 5 spans per side, a latency increase above both 20% and 10 ms, or
any error-rate increase. [Thresholds and interpretation](docs/product.md).

## Before using it in an incident

This is a local tool for one trusted operator. It uses the dependencies and fault
families you declare; unknown faults can remain ambiguous. Comparable sampling
and workloads matter for trace comparisons. Passing the declared requests does
not test every possible application failure. Arbitrary code, shell commands,
YAML and Kubernetes mutations are not supported repairs.

[How diagnosis works](docs/algorithms.md) · [Reproducible experiments and failures](docs/results.md) · [Design](docs/design.md) · [Contributing](CONTRIBUTING.md)

MIT licensed. The core uses the standard library; web and model dependencies are optional.
