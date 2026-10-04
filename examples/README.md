# Analyze a recorded application failure

`trace-export.json` contains real spans recorded by the disposable HTTP/SQLite lab
after injecting an incorrect catalog database path. It includes successful startup
liveness requests and the failed gateway business request. It contains no
production telemetry. Loopback URLs are historical fixture addresses, not live
targets to connect to.

```bash
opsresolve trace examples/trace-export.json
```

The deepest recorded failed operation is `catalog` / `database.read`, with
`error.type=OperationalError`. Failed parent HTTP operations are marked as error
propagation. A recorded origin is still a candidate until an intervention verifies
the cause; the full recovery lab performs that additional step.
