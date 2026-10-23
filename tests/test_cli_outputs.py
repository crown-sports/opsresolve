"""A saved report must not destroy the user's source or incident history."""

import json
import sys
from pathlib import Path

import pytest

from opsresolve.cli import main


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> int:
    monkeypatch.setattr(sys, "argv", ["opsresolve", *arguments])
    return main()


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_trace_export_preserves_input_aliases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], alias: str
) -> None:
    source = tmp_path / "traces.json"
    original = b'{"resourceSpans": []}\n'
    source.write_bytes(original)
    destination = source if alias == "same" else tmp_path / "report.json"
    if alias == "symlink":
        destination.symlink_to(source)
    elif alias == "hardlink":
        destination.hardlink_to(source)
    assert invoke(monkeypatch, "trace", str(source), "--output", str(destination)) == 2
    assert source.read_bytes() == original
    assert "must not overwrite" in capsys.readouterr().err


def test_diagnosis_does_not_start_when_report_would_replace_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = tmp_path / "target.json"
    original = b'{"version": 1, "name": "Own fixture"}\n'
    manifest.write_bytes(original)
    state = tmp_path / "state"
    assert invoke(monkeypatch, "diagnose", str(manifest), "--state", str(state), "--report", str(manifest)) == 2
    assert manifest.read_bytes() == original
    assert not state.exists()


def test_report_cannot_replace_incident_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    database = tmp_path / "incidents.sqlite3"
    database.write_bytes(b"sentinel database")
    assert invoke(monkeypatch, "report", "incident", "--state", str(tmp_path), "--output", str(database)) == 2
    assert database.read_bytes() == b"sentinel database"


def test_trace_export_creates_new_report_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "examples" / "trace-export.json"
    output = tmp_path / "reports" / "incident" / "traces.json"
    original = source.read_bytes()
    assert invoke(monkeypatch, "trace", str(source), "--format", "json", "--output", str(output)) == 0
    assert json.loads(output.read_text())["trace_count"] > 0
    assert source.read_bytes() == original
