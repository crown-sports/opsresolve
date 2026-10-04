"""OTLP validation, error propagation, and overlapping interval accounting."""

from pathlib import Path
from typing import Any

import pytest

from opsresolve.domain import ContractError, Probe
from opsresolve.lab import FaultLab
from opsresolve.probes import ProbeExecutor
from opsresolve.traces import analyze_traces, load_otlp


def envelope(spans: list[dict[str, Any]], service: str = "service") -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
                "scopeSpans": [{"spans": spans}],
            }
        ]
    }


def span(key: int, parent: int, left: int, right: int, failed: bool = False) -> dict[str, Any]:
    return {
        "traceId": "a" * 32,
        "spanId": f"{key:016x}",
        "parentSpanId": f"{parent:016x}" if parent else "",
        "name": f"operation {key}",
        "startTimeUnixNano": str(left * 10**6),
        "endTimeUnixNano": str(right * 10**6),
        "status": {"code": 2 if failed else 1},
    }


def test_parallel_children_are_not_double_counted() -> None:
    report = analyze_traces(envelope([span(1, 0, 0, 100), span(2, 1, 10, 70), span(3, 1, 40, 90)]))
    parent = next(item for item in report["spans"] if item["span_id"] == "0000000000000001")
    assert parent["exclusive_ms"] == 20
    assert report["services"][0]["exclusive_ms"] == 130


def test_deepest_error_is_separate_from_propagation() -> None:
    first = envelope([span(1, 0, 0, 100, True)], "gateway")
    second = envelope([span(2, 1, 10, 80, True), span(3, 2, 20, 60, True)], "database")
    report = analyze_traces({"resourceSpans": first["resourceSpans"] + second["resourceSpans"]})
    assert len(report["origins"]) == 1
    assert report["origins"][0]["span_id"] == "0000000000000003"
    assert report["services"][0]["service"] == "database"
    assert report["dependencies"] == [{"source": "gateway", "target": "database", "calls": 1, "failed_calls": 1}]


def test_missing_parents_are_visible_and_cycles_rejected() -> None:
    assert analyze_traces(envelope([span(2, 1, 10, 20, True)]))["warnings"]
    with pytest.raises(ContractError, match="cyclic"):
        analyze_traces(envelope([span(1, 2, 0, 100), span(2, 1, 0, 100)]))
    with pytest.raises(ContractError, match="duplicate"):
        analyze_traces(envelope([span(1, 0, 0, 100), span(1, 0, 0, 90)]))


def test_jsonlines_export_and_invalid_ids(tmp_path: Path) -> None:
    import json

    path = tmp_path / "export.ndjson"
    path.write_text(json.dumps(envelope([span(1, 0, 0, 10)])) + "\n" + json.dumps(envelope([span(2, 1, 1, 5)])))
    assert analyze_traces(load_otlp(path))["span_count"] == 2
    invalid = span(1, 0, 0, 10)
    invalid["traceId"] = "0" * 32
    with pytest.raises(ContractError):
        analyze_traces(envelope([invalid]))


def test_actual_http_sqlite_failure_emits_recorded_origin() -> None:
    with FaultLab() as lab:
        lab.inject([("database", lab.database_bindings[0])])
        result = ProbeExecutor(lab.target).run(Probe("http/gateway", "http", "gateway", 1))
        assert result.outcome == "failure"
        report = analyze_traces(lab.export_traces())
        assert report["failed_trace_count"] >= 1
        origins = [item for item in report["origins"] if item["operation"] == "database.read"]
        assert origins and origins[0]["attributes"]["error.type"] == "OperationalError"
        assert origins[0]["service"] == "catalog"
        assert any(item["propagated_error"] for item in report["spans"] if item["failed"])
