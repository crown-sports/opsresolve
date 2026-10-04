"""Explicit observations exercise incomplete, conflicting, and masked multi-fault explanations."""

from pathlib import Path

from opsresolve.diagnosis import DiagnosisModel
from opsresolve.domain import Observation, Target
from opsresolve.journal import Journal
from opsresolve.workflow import Investigation


def target(root: Path) -> Target:
    return Target.from_dict(
        {
            "version": 1,
            "name": "Chain",
            "entry": "front",
            "services": [{"id": key, "url": f"http://localhost:12345/{key}"} for key in ("front", "api", "db")],
            "dependencies": [
                {"source": "front", "target": "api"},
                {"source": "api", "target": "db"},
            ],
            "bindings": [
                {
                    "id": "route",
                    "service": "front",
                    "file": "front.json",
                    "pointer": "/url",
                    "expected": {"url_of": "api"},
                },
                {
                    "id": "database",
                    "service": "db",
                    "file": "db.json",
                    "pointer": "/path",
                    "expected": "db.sqlite3",
                },
            ],
        },
        root,
    )


def evidence(probe: str, outcome: str) -> Observation:
    kind, subject = probe.split("/")
    return Observation("ev_" + probe, probe, kind, subject, outcome, "2026-01-01T00:00:00+00:00", 1, {})


def test_unknown_checks_do_not_establish_health(tmp_path: Path) -> None:
    model = DiagnosisModel(target(tmp_path))
    assert model.report("budget_exhausted", 0, 1)["state"] == "needs_evidence"
    initial = len(model.worlds)
    model.observe(evidence("http/front", "unknown"))
    assert len(model.worlds) == initial
    assert model.report("no_probe", 1, 1)["state"] == "needs_evidence"


def test_healthy_entry_under_required_dependency_model(tmp_path: Path) -> None:
    model = DiagnosisModel(target(tmp_path))
    model.observe(evidence("http/front", "ok"))
    assert model.report("no_probe", 1, 8)["state"] == "healthy"
    assert model.choose(7) is None


def test_masked_fault_still_has_informative_probes(tmp_path: Path) -> None:
    model = DiagnosisModel(target(tmp_path))
    model.observe(evidence("http/front", "failure"))
    model.observe(evidence("config/route", "drift"))
    assert model.minimal_worlds() == [frozenset({"config/route"})]
    assert model.choose(4) is not None
    model.observe(evidence("http/api", "failure"))
    model.observe(evidence("config/database", "drift"))
    report = model.report("no_probe", 2.5, 8)
    assert report["explanations"] == [["config/database", "config/route"]]
    assert report["state"] == "diagnosed"
    own = next(fault for fault in report["faults"] if fault["id"] == "config/route")
    assert own["evidence_ids"] == ["ev_config/route"]


def test_conflict_is_not_a_guessed_diagnosis(tmp_path: Path) -> None:
    model = DiagnosisModel(target(tmp_path))
    model.observe(evidence("http/front", "ok"))
    model.observe(evidence("config/route", "drift"))
    assert model.report("conflict", 1.25, 8)["state"] == "model_conflict"
    assert model.choose(8) is None


def test_inadequate_budget_is_visible(tmp_path: Path) -> None:
    work = Investigation(target(tmp_path), Journal(tmp_path / "journal.sqlite3"))
    key = work.create(budget=0.5)
    record = work.run(key)
    assert record["observations"] == []
    assert record["state"] == "needs_evidence"
