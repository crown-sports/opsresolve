"""Compare actual OTLP structures, including unequal coverage and gate exit behavior."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_traces import envelope, span

from opsresolve.domain import ContractError
from opsresolve.trace_compare import compare_traces, comparison_markdown


def sample(duration=100, failed=0, count=10, service="api", operation="GET /orders"):
    spans = [span(i + 1, 0, 0, duration, i < failed) for i in range(count)]
    for item in spans:
        item["name"] = operation
    return envelope(spans, service)


def test_regression_reports_matched_operation_and_independent_reasons():
    report = compare_traces(sample(), sample(150, failed=2))
    assert report["state"] == "regression"
    row = report["operations"][0]
    assert row["reasons"] == ["p95_latency", "error_rate"]
    assert row["p95_delta_ms"] == 50 and row["error_rate_delta_pp"] == 20
    assert report["before_sha256"] != report["after_sha256"]
    assert "regression" in comparison_markdown(report)


def test_missing_operations_and_small_samples_never_claim_recovery():
    assert compare_traces(sample(count=1), sample(count=1))["state"] == "insufficient_evidence"
    report = compare_traces(sample(failed=10), sample(service="other"))
    assert report["state"] == "insufficient_evidence"
    assert {row["status"] for row in report["operations"]} == {"added", "missing"}


def test_thresholds_require_both_relative_and_absolute_latency_increase():
    assert compare_traces(sample(1), sample(2))["state"] == "no_regression"
    assert compare_traces(sample(100), sample(120))["state"] == "no_regression"
    assert compare_traces(sample(100, failed=2), sample(110, failed=1))["state"] == "no_regression"
    assert compare_traces(sample(0), sample(11))["state"] == "regression"


@pytest.mark.parametrize(
    "kwargs", [{"min_spans": True}, {"min_spans": 0}, {"latency_increase_pct": float("nan")}, {"error_increase_pp": -1}]
)
def test_invalid_thresholds_are_rejected(kwargs):
    with pytest.raises(ContractError):
        compare_traces(sample(), sample(), **kwargs)


def test_duplicate_spans_are_not_counted_twice_and_markdown_escapes_names():
    before = sample(operation="GET | orders")
    before["resourceSpans"][0]["scopeSpans"][0]["spans"] *= 2
    report = compare_traces(before, sample(operation="GET | orders"))
    assert report["operations"][0]["before"]["spans"] == 10
    assert report["warnings"]["before"]
    assert "GET \\| orders" in comparison_markdown(report)


def test_cli_gate_exits_one_with_machine_readable_evidence(tmp_path: Path):
    old, new = tmp_path / "before.json", tmp_path / "after.json"
    old.write_text(json.dumps(sample()))
    new.write_text(json.dumps(sample(300)))
    command = [
        sys.executable,
        "-m",
        "opsresolve.cli",
        "trace-compare",
        str(old),
        str(new),
        "--format",
        "json",
        "--check",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["regression_count"] == 1


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_cli_never_overwrites_an_input_export(tmp_path: Path, alias):
    before, after, output = tmp_path / "before.json", tmp_path / "after.json", tmp_path / "output.json"
    payload = json.dumps(sample())
    before.write_text(payload)
    after.write_text(payload)
    if alias == "same":
        output = before
    elif alias == "symlink":
        output.symlink_to(before)
    else:
        output.hardlink_to(before)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "opsresolve.cli",
            "trace-compare",
            str(before),
            str(after),
            "--output",
            str(output),
            "--format",
            "json",
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "overwrite" in result.stderr
    assert before.read_text() == after.read_text() == payload
