"""Validate diagnosis and recovery against real HTTP processes and SQLite business requests."""

from pathlib import Path
from typing import Any

import pytest

from opsresolve.domain import Target, canonical, strict_json
from opsresolve.journal import Journal
from opsresolve.lab import FaultLab
from opsresolve.repair import RepairTransaction
from opsresolve.workflow import Investigation


def investigate(lab: FaultLab, root: Path, policy: str = "active", budget: float = 8) -> tuple[Journal, dict[str, Any]]:
    journal = Journal(root / "incidents.sqlite3")
    work = Investigation(lab.target, journal)
    key = work.create(budget=budget, policy=policy)
    return journal, work.run(key)


@pytest.mark.parametrize("topology", ["fanout", "chain", "diamond"])
def test_two_hidden_faults_recover_all_services(tmp_path: Path, topology: str) -> None:
    with FaultLab(topology=topology, seed=73, opaque_names=True) as lab:
        lab.scenario("hidden_pair")
        journal, record = investigate(lab, tmp_path)
        assert record["diagnosis"]["explanations"] == [lab.faults]
        assert record["spent"] < sum(service.cost * 2 for service in lab.target.services) + sum(
            binding.cost for binding in lab.target.bindings
        )
        transaction = RepairTransaction(lab.target, journal)
        plan = transaction.prepare(record["id"])
        assert plan["can_apply"] and len(plan["changes"]) == 2
        result = transaction.apply(record["id"], plan["id"])
        assert result["state"] == "verified"
        assert len(result["checks"]) == 10
        assert all(item["outcome"] == "ok" and item["facts"]["status"] == 200 for item in result["checks"])
        assert journal.verify(record["id"])


def test_stale_file_refuses_every_change(tmp_path: Path) -> None:
    with FaultLab() as lab:
        lab.scenario("hidden_pair")
        journal, record = investigate(lab, tmp_path)
        transaction = RepairTransaction(lab.target, journal)
        plan = transaction.prepare(record["id"])
        path = lab.root / plan["changes"][-1]["file"]
        external = path.read_bytes() + b" "
        path.write_bytes(external)
        captured = {change["file"]: (lab.root / change["file"]).read_bytes() for change in plan["changes"]}
        result = transaction.apply(record["id"], plan["id"])
        assert result["state"] == "refused"
        assert result["checks"] == []
        assert all((lab.root / relative).read_bytes() == data for relative, data in captured.items())


def test_remaining_fault_triggers_exact_rollback(tmp_path: Path) -> None:
    with FaultLab() as lab:
        lab.scenario("wrong_port")
        journal, record = investigate(lab, tmp_path)
        transaction = RepairTransaction(lab.target, journal)
        plan = transaction.prepare(record["id"])
        assert plan["can_apply"]
        path = lab.root / f"config/{lab.ids[-1]}.json"
        document = strict_json(path.read_bytes())
        document["application_failure"] = True
        path.write_text(canonical(document))
        captured = {change["file"]: (lab.root / change["file"]).read_bytes() for change in plan["changes"]}
        result = transaction.apply(record["id"], plan["id"])
        assert result["state"] == "rolled_back"
        assert any(item["outcome"] != "ok" for item in result["checks"])
        assert all((lab.root / relative).read_bytes() == data for relative, data in captured.items())
        assert strict_json(path.read_bytes())["application_failure"] is True


@pytest.mark.parametrize("kind", ["application", "unavailable"])
def test_process_and_local_failures_require_operator_action(tmp_path: Path, kind: str) -> None:
    with FaultLab() as lab:
        lab.inject([(kind, lab.ids[-1])])
        journal, record = investigate(lab, tmp_path)
        assert record["diagnosis"]["explanations"] == [lab.faults]
        plan = RepairTransaction(lab.target, journal).prepare(record["id"])
        assert not plan["can_apply"]
        assert plan["blocked"]


def test_changed_target_intent_is_refused(tmp_path: Path) -> None:
    with FaultLab() as lab:
        lab.scenario("wrong_port")
        journal, record = investigate(lab, tmp_path)
        transaction = RepairTransaction(lab.target, journal)
        plan = transaction.prepare(record["id"])
        manifest = lab.target.to_dict()
        manifest["name"] = "Changed intent"
        other = Target.from_dict(manifest, lab.root)
        result = RepairTransaction(other, journal).apply(record["id"], plan["id"])
        assert result["state"] == "refused"
        assert "intent" in result["error"]
