# Use OpsResolve on an application

## Start with the question you need answered

“Is this endpoint reachable?” needs one URL. “Which required dependency or
configuration setting explains my failing request?” needs a target manifest.
“Where did an error begin in my recorded requests?” needs an OTLP JSON export.
The first release does not discover endpoints or source-code semantics by itself.

```bash
opsresolve init --url http://127.0.0.1:3000/orders --name Orders --output target.json
opsresolve diagnose target.json --budget 8 --report incident.md
opsresolve serve --target target.json
```

The URL must have no embedded credentials, query parameters, or fragment. Add
HTTP authentication through `headers_env` in the manifest, never by embedding
a secret in the URL. Those environment values are used for requests, not exported
in reports. Response text has best-effort credential redaction; review sensitive
data before configuring any remote model endpoint.

## Declare required business dependencies

Example `target.json`:

```json
{
  "version": 1,
  "name": "Order application",
  "entry": "api",
  "services": [
    {
      "id": "api",
      "name": "Order API",
      "url": "http://127.0.0.1:3000/orders",
      "health_url": "http://127.0.0.1:3000/health",
      "expected_status": 200,
      "body_contains": "orders",
      "timeout_seconds": 2,
      "cost": 1
    },
    {
      "id": "catalog",
      "url": "http://127.0.0.1:3001/items",
      "health_url": "http://127.0.0.1:3001/health",
      "headers_env": {"Authorization": "CATALOG_AUTHORIZATION"}
    }
  ],
  "dependencies": [{"source": "api", "target": "catalog"}],
  "bindings": [
    {
      "id": "catalog-route",
      "service": "api",
      "file": "config/api.json",
      "pointer": "/catalog_url",
      "expected": {"url_of": "catalog"},
      "cost": 0.25,
      "repairable": true,
      "reload": "hot"
    }
  ]
}
```

Here the application owner declares that `/orders` requires the catalog request.
The two business URLs should exercise the behavior you need restored. A green
liveness endpoint alone does not verify orders, queries, or dependency calls.
The separate liveness URL must bypass required business dependencies. Every
declared node must be reachable from the entry, and version 1 requires a DAG.

`config/api.json` is relative to the manifest's directory. Existing fields only;
JSON pointers support objects, arrays, `~0`, and `~1`. Expected values may be scalar
or a declared service URL. The binding must actually affect the declared service
business check; arbitrary cosmetic settings do not satisfy the propagation model.

If your application needs a restart to load the setting, use `reload: "manual"`.
Such changes receive an operator action and cannot be automatically applied by
this release. Sensitive pointers and bindings are never automatically repaired.

## Diagnose, review, then intervene

```bash
opsresolve diagnose target.json --budget 8 --max-faults 2 --report incident.md
opsresolve repair target.json --incident INCIDENT_ID
opsresolve repair target.json --incident INCIDENT_ID --apply
```

Use the same `--state` directory across commands if you override its default.
The second command displays the stored plan. `--apply` performs precisely that
plan, not a newly generated arbitrary action. In the browser, real targets are
read-only until the owner starts:

```bash
opsresolve serve --target target.json --allow-repair
```

The executor checks source evidence, target intent, plan age, current file hashes,
and exact field values before writing. Plans expire after five minutes. All
declared business endpoints are checked twice after writing. Unknown or failed
checks cause rollback. JSON serialization preserves other values but may change
formatting; original bytes are retained in backups. Ownership and permissions are
preserved. Rollback refuses to overwrite a detected intervening external edit.

Configuration directories must be trusted. Other writers should coordinate using
the `.opsresolve/repair.lock` lock. Hash checks do not make concurrent uncooperative
writers or malicious directory replacement safe. The first release is a local
operator tool, not a privileged multi-user control plane.

## Interrupted transactions

Before mutation, each transaction records backup mappings and before/after hashes
under the target workspace's `.opsresolve/tx_.../transaction.json`.

```bash
opsresolve recover target.json
opsresolve recover target.json --apply
```

The first command reviews candidate restores. The second restores only files
still matching this engine's proposed bytes, leaving conflicting external changes
for the operator. The runtime tests include an actual SIGKILL after the first
configuration write. This is process-interruption recovery, not a claim of global
atomicity or comprehensive power-loss durability.

## Analyze existing traces

```bash
opsresolve trace collector-export.json --output trace-report.md
opsresolve trace collector-export.ndjson --format json --output trace-report.json
```

The UI's **Import OTLP JSON** accepts the same complete OTLP JSON or collector
JSON-lines envelopes, up to 5 MiB / 5,000 spans. It processes them locally without
calling a model. It accepts `resourceSpans`, `scopeSpans`, hexadecimal IDs, and
nanosecond timestamps. Jaeger-specific JSON and binary protobuf are not accepted.

Outputs include deepest recorded error spans, propagated error spans, observed
service edges, per-service span counts and p95 span duration, and exclusive time
after subtracting overlapping same-service child intervals. These are recorded
observations, not a learned causal graph, CPU measurements, or a distributed
critical path. A missing child span can make an upstream failure look like an
origin; missing parents and incomplete traces are reported.

## Optional local explanation

Use an existing Ollama installation with a locally available model:

```bash
opsresolve serve --demo --model-url http://127.0.0.1:11434 --model qwen3:4b
```

Or use an operator-downloaded Hugging Face model directory:

```bash
python -m pip install -e '.[web,model]'
opsresolve model-serve --path /path/to/local/model --device cuda --port 8766
opsresolve serve --demo --model-url http://127.0.0.1:8766 --model local-qwen
```

The bundled server loads local files only with remote model code disabled. CUDA
installation must match your hardware; the published run used Torch 2.8.0+cu128,
Transformers 4.57.6, and a pinned Qwen3-4B-Instruct-2507 snapshot. See the experiment
record. Diagnosis and repair work without the model. Accepted prose is still an
interpretation: identifier/quote checks do not prove its semantic correctness.

## Remote and persistent use

The workbench binds to `127.0.0.1`. Forward its port from a remote host with your
existing SSH configuration. Browser requests use a session cookie, same-origin
action token, bounded inputs, and a loopback Host allowlist. There is no multi-user
authentication or tenant authorization in this version.

Incidents and event chains persist in `~/.opsresolve/incidents.sqlite3`; changing
the state directory creates a separate history. Demo workspaces are disposable,
but their incident reports remain readable after processes stop. Event-chain
hashes detect changed links; database owners can replace and rehash records.

## Saving reports on main

The next patch protects your inputs when saving a report. An output path cannot
refer to its input trace, target manifest or incident database, even through a
symlink or hardlink. Choose a separate report path; new parent directories are
created automatically. Existing report files can still be updated at the path
you specify. These changes are on main and are not part of v0.2.0.

```sh
opsresolve trace collector-export.json --output reports/incident/trace-report.md
```
