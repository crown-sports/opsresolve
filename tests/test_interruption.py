"""Actual process death and foreign-writer conflicts exercise durable repair recovery."""

import subprocess
import sys
from pathlib import Path
from typing import Any

from opsresolve.domain import canonical, strict_json
from opsresolve.journal import Journal
from opsresolve.lab import FaultLab
from opsresolve.probes import ProbeExecutor
from opsresolve.repair import RepairTransaction
from opsresolve.workflow import Investigation


def setup(lab: FaultLab, root: Path) -> tuple[Journal, dict[str, Any], dict[str, Any]]:
    journal = Journal(root / "incidents.sqlite3")
    work = Investigation(lab.target, journal)
    key = work.create()
    record = work.run(key)
    plan = RepairTransaction(lab.target, journal).prepare(key)
    return journal, record, plan


def test_sigkill_after_first_write_is_reviewable_and_recoverable(tmp_path: Path) -> None:
    with FaultLab() as lab:
        lab.scenario("hidden_pair")
        journal, record, plan = setup(lab, tmp_path)
        originals = {change["file"]: (lab.root / change["file"]).read_bytes() for change in plan["changes"]}
        script = """
import os, signal, sys
from pathlib import Path
import opsresolve.repair as repair
from opsresolve.domain import Target
from opsresolve.journal import Journal
original = repair.atomic_write
def interrupted(path, data, mode):
    original(path, data, mode)
    if path.parent.name == 'config':
        os.kill(os.getpid(), signal.SIGKILL)
repair.atomic_write = interrupted
repair.RepairTransaction(Target.load(Path(sys.argv[1])), Journal(Path(sys.argv[2]))).apply(sys.argv[3],sys.argv[4])
"""
        child = subprocess.run(
            [sys.executable, "-c", script, str(lab.manifest), str(journal.path), record["id"], plan["id"]],
            capture_output=True,
            timeout=10,
        )
        assert child.returncode == -9
        transaction = RepairTransaction(lab.target, journal)
        assert len(transaction.pending()) == 1
        review = transaction.recover()
        assert review[0]["restored_files"] and not review[0]["applied"]
        assert any((lab.root / relative).read_bytes() != data for relative, data in originals.items())
        recovered = transaction.recover(apply=True)
        assert recovered[0]["state"] == "rolled_back"
        assert all((lab.root / relative).read_bytes() == data for relative, data in originals.items())
        assert not transaction.pending()
        assert journal.get(record["id"])["state"] == "rolled_back"


def test_rollback_does_not_overwrite_a_foreign_edit(tmp_path: Path, monkeypatch: Any) -> None:
    with FaultLab() as lab:
        lab.scenario("wrong_port")
        journal, record, plan = setup(lab, tmp_path)
        path = lab.root / plan["changes"][0]["file"]
        real_run = ProbeExecutor.run
        attempts = 0

        def changed(executor: ProbeExecutor, probe: Any) -> Any:
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                document = strict_json(path.read_bytes())
                document["external_edit"] = True
                document["application_failure"] = True
                path.write_text(canonical(document))
            return real_run(executor, probe)

        monkeypatch.setattr(ProbeExecutor, "run", changed)
        result = RepairTransaction(lab.target, journal).apply(record["id"], plan["id"])
        assert result["state"] == "manual_recovery"
        assert result["rollback_conflicts"] == [plan["changes"][0]["file"]]
        assert strict_json(path.read_bytes())["external_edit"] is True
