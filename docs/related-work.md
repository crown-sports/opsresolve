# Related work and honest scope

Reviewed 2026-10-04. Links identify primary sources; this is a capability context,
not an assertion that another project's entire codebase lacks a feature.

[AIOpsLab](https://github.com/microsoft/AIOpsLab) provides interactive application
deployment, fault injection, telemetry, and agent evaluation. It is relevant prior
work for runtime-verified operations tasks. OpsResolve's small HTTP/SQLite lab is
much narrower and does not replace a Kubernetes benchmark suite.

[RCAEval](https://github.com/phamquiluan/RCAEval) provides root-cause analysis
datasets and evaluation resources. This release has not been evaluated on RCAEval.
The published development fixtures must not be interpreted as an external RCA
benchmark or production accuracy estimate.

[HolmesGPT](https://github.com/HolmesGPT/holmesgpt) is an existing SRE investigation
agent. SRE assistance and tool-guided investigation are established product areas.
OpsResolve concentrates on a small deterministic consistency model, inspectable
probe ordering, bounded configuration interventions, and a local workbench.

[OpenClaw](https://github.com/openclaw/openclaw),
[Hermes](https://github.com/NousResearch/hermes-agent), and
[OpenHands](https://github.com/OpenHands/OpenHands) are general agent systems.
Their tools, skills, or integrations can support operations workflows. No benchmark
here compares complete agents or establishes that they cannot implement this flow.

[OTLP JSON encoding](https://opentelemetry.io/docs/specs/otlp/)
defines the imported trace envelope. The importer uses hexadecimal span/trace IDs
and integer nanosecond timestamps; it does not accept arbitrary trace formats.
[HTTP semantic conventions](https://opentelemetry.io/docs/specs/semconv/http/http-spans/)
describe client/server span behavior. Our visible HTTP-failure analysis predicate
also counts recorded 4xx responses; this is not a claim that every SDK marks them
as server errors.

The optional chat adapter follows the native
[Ollama chat API](https://github.com/ollama/ollama/blob/main/docs/api.md).
The actual published model experiment uses the official
[Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
snapshot and local Transformers inference, not an unreported hosted model.

Model-based diagnosis, minimum consistent explanations, and information-driven
test selection are established ideas. The technical work in this release is the
integration contract: explicit unknowns and model conflict, retained multi-fault
worlds, evidence-linked field preconditions, guarded rollback, recorded trace
origins, and recovery established by business requests. It is engineering value,
not a claim of a new causal discovery theory.
