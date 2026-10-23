# Changelog

## Unreleased

Refuse CLI report paths that would overwrite a trace export, target manifest or incident database, including symlink and hardlink aliases. Create missing report directories and write UTF-8 exports.

## 0.2.0 — 2026-10-22 (prerelease)

Add offline before/after OTLP regression comparison, per-operation evidence gaps, configurable latency/error thresholds and a CI exit gate. Preserve input exports when output paths alias them. Compare integer counts and nanosecond durations exactly so equality with a configured budget never becomes a floating-point regression.

## 0.1.0

Initial GitHub prerelease. Historical experiment results remain attributed to that version.
