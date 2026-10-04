# Contributing

Make the first successful use clear: input, observed problem, proposed action,
and independently checked outcome. Add a real runtime reproduction for a new
fault adapter. Do not infer success from a model answer alone.

Domain contracts and diagnosis stay independent of UI and provider SDKs. Add typed
read-only probe strategies and bounded mutation adapters rather than accepting
model-generated shell commands. Public methods should document their input,
preconditions, output, and meaningful failure behavior; avoid narration of obvious
implementation details.

Run Ruff, Mypy, the relevant runtime tests, and package build checks. Keep private
manifests, credentials, host paths, incident stores, and model caches out of commits.
Record complete experiment denominators and source fingerprints. When an
algorithm does not improve a baseline, publish that outcome.

The next useful extensions are OTLP collector streaming, explicit models for
optional dependencies and intermittent failures, additional configuration adapters
with reload/rollback contracts, and evaluation on separately licensed external
incident corpora. These are future work, not current capabilities.
