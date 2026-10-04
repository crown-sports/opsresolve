"""Offline OTLP JSON investigation: failure origins, dependency edges, and exclusive span time."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .domain import ContractError, canonical, digest, strict_json
from .probes import redact


@dataclass(frozen=True)
class Span:
    trace_id: str
    span_id: str
    parent_id: str
    service: str
    name: str
    start_ns: int
    end_ns: int
    failed: bool
    attributes: dict[str, Any]


def attributes(items: Any) -> dict[str, Any]:
    """Decode OTLP scalar attributes without treating trace content as executable instructions."""
    if not isinstance(items, list):
        raise ContractError("OTLP attributes must be a list")
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise ContractError("Invalid OTLP attribute")
        value = item.get("value", {})
        if not isinstance(value, dict):
            raise ContractError("Invalid OTLP attribute value")
        for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if key in value:
                result[item["key"]] = value[key]
                break
    return result


def parse_otlp(value: Any) -> list[Span]:
    """Validate complete JSON export envelopes with hexadecimal IDs and nanosecond timestamps."""
    try:
        return _parse_otlp(value)
    except ContractError:
        raise
    except (AttributeError, TypeError, ValueError, KeyError) as exc:
        raise ContractError("Malformed OTLP JSON span structure") from exc


def _parse_otlp(value: Any) -> list[Span]:
    """Decode the supported OTLP fields after normalizing structural failures."""
    if not isinstance(value, dict) or not isinstance(value.get("resourceSpans"), list):
        raise ContractError("Expected an OTLP JSON object containing resourceSpans")
    spans = []
    for resource in value["resourceSpans"]:
        resource_attributes = attributes(resource.get("resource", {}).get("attributes", []))
        service = resource_attributes.get("service.name", "unknown-service")
        if not isinstance(service, str) or not 1 <= len(service) <= 160:
            raise ContractError("Invalid service.name")
        for scope in resource.get("scopeSpans", []):
            for item in scope.get("spans", []):
                if not isinstance(item, dict):
                    raise ContractError("Invalid OTLP span")
                trace_id, span_id = item.get("traceId"), item.get("spanId")
                parent = item.get("parentSpanId", "")
                if not isinstance(parent, str):
                    raise ContractError("parentSpanId must be a hexadecimal string")
                if (
                    not isinstance(trace_id, str)
                    or not re.fullmatch(r"[0-9a-fA-F]{32}", trace_id)
                    or int(trace_id, 16) == 0
                ):
                    raise ContractError("OTLP traceId must be a nonzero 32-character hex string")
                if (
                    not isinstance(span_id, str)
                    or not re.fullmatch(r"[0-9a-fA-F]{16}", span_id)
                    or int(span_id, 16) == 0
                ):
                    raise ContractError("OTLP spanId must be a nonzero 16-character hex string")
                if parent and (not isinstance(parent, str) or not re.fullmatch(r"[0-9a-fA-F]{16}", parent)):
                    raise ContractError("Invalid OTLP parentSpanId")
                try:
                    start = int(item["startTimeUnixNano"])
                    end = int(item["endTimeUnixNano"])
                except (ValueError, TypeError, KeyError) as exc:
                    raise ContractError("Span needs integer nanosecond timestamps") from exc
                if start < 0 or end < start or end - start > 86400 * 10**9:
                    raise ContractError("Invalid span interval")
                name = item.get("name", "unnamed operation")
                if not isinstance(name, str) or len(name) > 512:
                    raise ContractError("Invalid span name")
                raw = attributes(item.get("attributes", []))
                visible = {}
                for key, content in raw.items():
                    if key.startswith(("http.", "server.", "db.", "error.")) and not re.search(
                        r"password|token|secret|authorization|statement|query", key, re.I
                    ):
                        visible[key] = redact(str(content))[:500]
                code = item.get("status", {}).get("code", 0)
                status = raw.get("http.response.status_code", raw.get("http.status_code", 0))
                try:
                    http_failure = int(status) >= 400
                except (ValueError, TypeError):
                    http_failure = False
                failed = code in {2, "2", "STATUS_CODE_ERROR"} or http_failure
                spans.append(
                    Span(
                        trace_id.lower(),
                        span_id.lower(),
                        parent.lower() if parent and int(parent, 16) else "",
                        redact(service),
                        redact(name),
                        start,
                        end,
                        failed,
                        visible,
                    )
                )
                if len(spans) > 5000:
                    raise ContractError("Trace analysis accepts at most 5,000 spans")
    if not spans:
        raise ContractError("Export contains no spans")
    return spans


def load_otlp(path: Path) -> Any:
    """Read a bounded JSON or collector JSON-lines export without requiring a live collector."""
    with path.open("rb") as stream:
        data = stream.read(5242881)
    if len(data) > 5242880:
        raise ContractError("Trace exports must be at most 5 MiB")
    try:
        return strict_json(data)
    except ContractError:
        envelopes = [strict_json(line) for line in data.splitlines() if line.strip()]
        if not envelopes or not all(
            isinstance(item, dict) and isinstance(item.get("resourceSpans"), list) for item in envelopes
        ):
            raise ContractError("Expected OTLP JSON or one OTLP export envelope per line") from None
        return {"resourceSpans": [resource for item in envelopes for resource in item["resourceSpans"]]}


def union_duration(intervals: list[tuple[int, int]]) -> int:
    """Measure overlapping child intervals once, avoiding negative exclusive time for parallel calls."""
    total = 0
    end = -1
    for left, right in sorted(intervals):
        if right <= left:
            continue
        total += max(0, right - max(left, end))
        end = max(end, right)
    return total


def analyze_traces(value: Any) -> dict[str, Any]:
    """Separate deepest recorded failures from propagated errors and summarize observed work."""
    raw_spans = parse_otlp(value)
    indexed: dict[tuple[str, str], Span] = {}
    warnings: list[str] = []
    for span in raw_spans:
        key = (span.trace_id, span.span_id)
        if key in indexed and indexed[key] != span:
            raise ContractError("Conflicting duplicate span identity")
        if key in indexed:
            warnings.append("Identical duplicate spans were deduplicated")
        indexed[key] = span
    children: dict[tuple[str, str], list[Span]] = defaultdict(list)
    missing = 0
    for span in indexed.values():
        if span.parent_id:
            parent_key = (span.trace_id, span.parent_id)
            if parent_key in indexed:
                children[parent_key].append(span)
            else:
                missing += 1
    if missing:
        warnings.append(f"{missing} spans have missing parents; sampled or incomplete traces can conceal origins")
    descendant_error: dict[tuple[str, str], bool] = {}
    active: set[tuple[str, str]] = set()

    def errors_below(span: Span, depth: int = 0) -> bool:
        key = (span.trace_id, span.span_id)
        if key in descendant_error:
            return descendant_error[key]
        if key in active or depth > 200:
            raise ContractError("Span parent graph is cyclic or exceeds 200 levels")
        active.add(key)
        bad = False
        for child in children[key]:
            child_bad = errors_below(child, depth + 1)
            bad = bad or child.failed or child_bad
        active.remove(key)
        descendant_error[key] = bad
        return bad

    for span in indexed.values():
        errors_below(span)
    origins = []
    services: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    durations: dict[str, list[float]] = defaultdict(list)
    span_records = []
    for span in indexed.values():
        key = (span.trace_id, span.span_id)
        same_process_children = [child for child in children[key] if child.service == span.service]
        intervals = [
            (max(span.start_ns, child.start_ns), min(span.end_ns, child.end_ns)) for child in same_process_children
        ]
        exclusive = max(0, span.end_ns - span.start_ns - union_duration(intervals)) / 10**6
        duration = (span.end_ns - span.start_ns) / 10**6
        durations[span.service].append(duration)
        item = services.setdefault(
            span.service,
            {
                "service": span.service,
                "spans": 0,
                "failed_spans": 0,
                "origin_spans": 0,
                "exclusive_ms": 0.0,
            },
        )
        item["spans"] += 1
        item["failed_spans"] += int(span.failed)
        item["exclusive_ms"] += exclusive
        record = {
            **asdict(span),
            "duration_ms": round(duration, 3),
            "exclusive_ms": round(exclusive, 3),
            "propagated_error": span.failed and descendant_error[key],
        }
        span_records.append(record)
        if span.failed and not descendant_error[key]:
            item["origin_spans"] += 1
            parent = indexed.get((span.trace_id, span.parent_id))
            origins.append(
                {
                    "trace_id": span.trace_id,
                    "span_id": span.span_id,
                    "service": span.service,
                    "operation": span.name,
                    "duration_ms": round(duration, 3),
                    "attributes": span.attributes,
                    "caller_service": parent.service if parent else None,
                    "evidence": "Deepest recorded failed span; missing instrumentation can hide another cause",
                }
            )
        parent = indexed.get((span.trace_id, span.parent_id))
        if parent and parent.service != span.service:
            edge = edges.setdefault(
                (parent.service, span.service),
                {"source": parent.service, "target": span.service, "calls": 0, "failed_calls": 0},
            )
            edge["calls"] += 1
            edge["failed_calls"] += int(span.failed)
    for name, item in services.items():
        times = sorted(durations[name])
        item["p95_span_ms"] = round(times[math.ceil(len(times) * 0.95) - 1], 3)
        item["exclusive_ms"] = round(item["exclusive_ms"], 3)
    by_trace: dict[str, list[Span]] = defaultdict(list)
    for span in indexed.values():
        by_trace[span.trace_id].append(span)
    traces = []
    for trace_id, members in by_trace.items():
        roots = [span for span in members if not span.parent_id or (trace_id, span.parent_id) not in indexed]
        traces.append(
            {
                "trace_id": trace_id,
                "spans": len(members),
                "failed": any(span.failed for span in members),
                "root_duration_ms": round(max((span.end_ns - span.start_ns for span in roots), default=0) / 10**6, 3),
            }
        )
    return {
        "kind": "trace_analysis",
        "trace_count": len(traces),
        "span_count": len(indexed),
        "failed_trace_count": sum(trace["failed"] for trace in traces),
        "origins": sorted(origins, key=lambda item: (-item["duration_ms"], item["service"])),
        "services": sorted(services.values(), key=lambda item: (-item["origin_spans"], -item["exclusive_ms"])),
        "dependencies": list(edges.values()),
        "traces": traces,
        "spans": span_records,
        "warnings": sorted(set(warnings)),
        "source_sha256": digest(canonical(value).encode()),
        "limits": (
            "Recorded failure origins are candidates, not intervention-proven causes. "
            "Exclusive time subtracts same-service child interval unions; it is not CPU time "
            "or a distributed critical path."
        ),
    }


def trace_markdown(report: dict[str, Any]) -> str:
    """Export observed origins and latency measurements without claiming automatic remediation."""
    lines = [
        "# Trace investigation",
        "",
        f"Traces: {report['trace_count']}; spans: {report['span_count']}; "
        f"failed traces: {report['failed_trace_count']}",
        "",
        "## Recorded error origins",
        "",
    ]
    for item in report["origins"]:
        lines.append(f"- {item['service']} · {item['operation']} · {item['duration_ms']} ms · span `{item['span_id']}`")
    lines.extend(
        [
            "",
            "## Service observations",
            "",
            "| Service | Recorded origins | Failed spans | Exclusive ms | p95 span ms |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in report["services"]:
        lines.append(
            f"| {item['service']} | {item['origin_spans']} | {item['failed_spans']} | "
            f"{item['exclusive_ms']} | {item['p95_span_ms']} |"
        )
    lines.extend(["", *report["warnings"], "", report["limits"], ""])
    return "\n".join(lines)
