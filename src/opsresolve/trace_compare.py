"""Compare recorded operations across two OTLP exports without inferring causality."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .domain import ContractError
from .traces import analyze_traces


def _operations(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for span in report["spans"]:
        groups[span["service"], span["name"]].append(span)
    result = {}
    for key, spans in groups.items():
        durations = sorted((span["end_ns"] - span["start_ns"]) / 1e6 for span in spans)
        errors = sum(bool(span["failed"]) for span in spans)
        result[key] = {
            "spans": len(spans),
            "failed_spans": errors,
            "error_rate": errors / len(spans),
            "p95_ms": durations[math.ceil(len(spans) * 0.95) - 1],
        }
    return result


def compare_traces(
    before: Any,
    after: Any,
    *,
    min_spans: int = 5,
    latency_increase_pct: float = 20,
    latency_increase_ms: float = 10,
    error_increase_pp: float = 0,
) -> dict[str, Any]:
    """Gate matched service/operation groups and expose missing or low-volume coverage."""
    if type(min_spans) is not int or min_spans < 1:
        raise ContractError("min_spans must be a positive integer")
    thresholds = (latency_increase_pct, latency_increase_ms, error_increase_pp)
    if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or n < 0 for n in thresholds):
        raise ContractError("Regression thresholds must be finite nonnegative numbers")
    previous, current = analyze_traces(before), analyze_traces(after)
    old, new = _operations(previous), _operations(current)
    rows = []
    for service, operation in sorted(old.keys() | new.keys()):
        left, right = old.get((service, operation)), new.get((service, operation))
        reasons = []
        if left is None or right is None:
            status = "added" if left is None else "missing"
        elif min(left["spans"], right["spans"]) < min_spans:
            status = "insufficient_samples"
        else:
            delta = right["p95_ms"] - left["p95_ms"]
            if delta > latency_increase_ms and delta > left["p95_ms"] * latency_increase_pct / 100:
                reasons.append("p95_latency")
            if (right["error_rate"] - left["error_rate"]) * 100 > error_increase_pp:
                reasons.append("error_rate")
            status = "regression" if reasons else "no_regression"
        rows.append(
            {
                "service": service,
                "operation": operation,
                "status": status,
                "reasons": reasons,
                "before": left,
                "after": right,
                "p95_delta_ms": right["p95_ms"] - left["p95_ms"] if left and right else None,
                "error_rate_delta_pp": (right["error_rate"] - left["error_rate"]) * 100 if left and right else None,
            }
        )
    regressions = sum(row["status"] == "regression" for row in rows)
    unverified = sum(row["status"] in {"added", "missing", "insufficient_samples"} for row in rows)
    return {
        "kind": "trace_comparison",
        "state": "regression" if regressions else "insufficient_evidence" if unverified else "no_regression",
        "regression_count": regressions,
        "unverified_count": unverified,
        "operations": rows,
        "thresholds": {
            "min_spans": min_spans,
            "latency_increase_pct": latency_increase_pct,
            "latency_increase_ms": latency_increase_ms,
            "error_increase_pp": error_increase_pp,
        },
        "before_sha256": previous["source_sha256"],
        "after_sha256": current["source_sha256"],
        "warnings": {"before": previous["warnings"], "after": current["warnings"]},
        "limits": (
            "Observed export samples, not traffic-normalized production rates or statistical significance. "
            "Matched by service and operation name. Missing operations do not prove recovery. "
            "Sampling, workload and instrumentation changes can alter comparisons; no causal attribution."
        ),
    }


def comparison_markdown(report: dict[str, Any]) -> str:
    """Render a reviewable comparison including evidence gaps and configured thresholds."""

    def escape(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    lines = [
        "# Trace regression comparison",
        "",
        f"Result: {report['state']}",
        "",
        "| Service / operation | Status | Spans before / after | p95 delta ms | Error delta pp |",
        "|---|---|---:|---:|---:|",
    ]
    for row in report["operations"]:
        left, right = row["before"], row["after"]
        count = f"{left['spans'] if left else '—'} / {right['spans'] if right else '—'}"
        latency = f"{row['p95_delta_ms']:+.3f}" if row["p95_delta_ms"] is not None else "—"
        errors = f"{row['error_rate_delta_pp']:+.3f}" if row["error_rate_delta_pp"] is not None else "—"
        lines.append(
            f"| {escape(row['service'])} / {escape(row['operation'])} | {row['status']} "
            f"| {count} | {latency} | {errors} |"
        )
    lines.extend(["", f"Thresholds: {report['thresholds']}", "", report["limits"], ""])
    for side, warnings in report["warnings"].items():
        lines.extend(f"- {side}: {escape(warning)}" for warning in warnings)
    return "\n".join(lines) + "\n"
