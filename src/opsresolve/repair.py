"""Evidence-bound JSON patch transactions with stale-plan refusal and verified rollback."""

from __future__ import annotations

import fcntl
import os
import stat
import tempfile
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .domain import (
    ContractError,
    Probe,
    Target,
    canonical,
    digest,
    identifier,
    pointer_get,
    pointer_set,
    safe_file,
    same_value,
    strict_json,
    timestamp,
)
from .journal import Journal
from .probes import ProbeExecutor


def build_plan(target: Target, record: dict[str, Any]) -> dict[str, Any]:
    """Propose only directly captured, nonsensitive, hot-reloaded configuration corrections."""
    diagnosis = record.get("diagnosis", {})
    blocked: list[str] = []
    changes = []
    if record["state"] != "diagnosed" or diagnosis.get("explanation_count") != 1:
        blocked.append("A unique minimum explanation is required before automatic repair")
    fault_ids = set(diagnosis.get("explanations", [[]])[0]) if diagnosis.get("explanations") else set()
    observed = {item["probe_id"]: item for item in record["observations"]}
    for key in sorted(fault_ids):
        if not key.startswith("config/"):
            blocked.append(f"{key} requires an operator action; no process control is permitted")
            continue
        binding = next(item for item in target.bindings if f"config/{item.id}" == key)
        evidence = observed.get(key)
        if not evidence or evidence["outcome"] != "drift":
            blocked.append(f"{key} is inferred but not directly observed")
            continue
        if binding.sensitive or not binding.repairable or binding.reload != "hot":
            blocked.append(f"{key} is sensitive, not enabled for repair, or needs a manual reload")
            continue
        facts = evidence["facts"]
        changes.append(
            {
                "binding_id": binding.id,
                "fault_id": key,
                "file": binding.file,
                "pointer": binding.pointer,
                "before": facts["current"],
                "after": target.expected_value(binding),
                "expected_sha256": facts["file_sha256"],
                "evidence_id": evidence["id"],
            }
        )
    hashes: dict[str, set[str]] = defaultdict(set)
    for change in changes:
        hashes[change["file"]].add(change["expected_sha256"])
    if any(len(values) != 1 for values in hashes.values()):
        blocked.append("A configuration file changed between probes; investigate again")
    return {
        "id": identifier("plan"),
        "created_at": timestamp(),
        "incident_id": record["id"],
        "target_digest": digest(canonical(target.to_dict()).encode()),
        "changes": changes,
        "can_apply": bool(changes) and not blocked,
        "blocked": blocked,
        "verification_services": [service.id for service in target.services],
        "verification_rounds": 2,
        "expires_after_seconds": 300,
        "note": "A successful intervention is required to establish recovery. Failed checks trigger rollback.",
    }


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    """Replace a local file while preserving ownership and flushing content and its directory entry."""
    existing = path.stat(follow_symlinks=False) if path.exists() else None
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise ContractError("Atomic writes require a regular destination file")
    descriptor, temporary = tempfile.mkstemp(prefix=".opsresolve-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if existing is not None:
                os.fchown(stream.fileno(), existing.st_uid, existing.st_gid)
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RepairTransaction:
    """Own the complete mutation lifecycle; controllers can submit only a stored plan identifier."""

    def __init__(self, target: Target, journal: Journal):
        self.target = target
        self.journal = journal

    def prepare(self, incident_id: str) -> dict[str, Any]:
        """Persist the exact changes and their evidence so the operator can review them."""
        record = self.journal.get(incident_id)
        plan = build_plan(self.target, record)
        record["plan"] = plan
        self.journal.append(incident_id, "plan_prepared", plan)
        self.journal.save(record)
        return plan

    def _validate_plan(self, record: dict[str, Any], plan_id: str) -> dict[str, Any]:
        plan: dict[str, Any] | None = record.get("plan")
        if not plan or plan["id"] != plan_id or not plan["can_apply"]:
            raise ContractError("No applicable stored repair plan")
        if record.get("repair") or record["state"] != "diagnosed":
            raise ContractError("This incident has already been repaired or is no longer diagnosed")
        if plan["target_digest"] != digest(canonical(self.target.to_dict()).encode()):
            raise ContractError("Target intent changed after diagnosis")
        age = (datetime.now(UTC) - datetime.fromisoformat(plan["created_at"])).total_seconds()
        if age < 0 or age > plan["expires_after_seconds"]:
            raise ContractError("Repair plan expired; investigate again")
        evidence = {item["id"]: item for item in record["observations"]}
        bindings = {item.id: item for item in self.target.bindings}
        for change in plan["changes"]:
            binding = bindings.get(change["binding_id"])
            captured = evidence.get(change["evidence_id"])
            if not binding or binding.sensitive or not binding.repairable or binding.reload != "hot":
                raise ContractError("Repair exceeds the target's allowed configuration contracts")
            if not captured or captured["probe_id"] != f"config/{binding.id}" or captured["outcome"] != "drift":
                raise ContractError("Repair has no directly observed drift evidence")
            facts = captured["facts"]
            if (
                change["file"] != binding.file
                or change["pointer"] != binding.pointer
                or change["expected_sha256"] != facts["file_sha256"]
                or not same_value(change["before"], facts["current"])
                or not same_value(change["after"], self.target.expected_value(binding))
            ):
                raise ContractError("Stored repair does not match its evidence and declared intent")
        return plan

    @contextmanager
    def _lock(self) -> Iterator[None]:
        """Serialize engine-controlled mutations and recovery in this configuration workspace."""
        state_directory = self.target.root / ".opsresolve"
        if state_directory.is_symlink():
            raise ContractError("Transaction directory must not be a symbolic link")
        state_directory.mkdir(mode=0o700, exist_ok=True)
        lock_path = state_directory / "repair.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a+b") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ContractError("Another repair is active in this workspace") from exc
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def apply(self, incident_id: str, plan_id: str) -> dict[str, Any]:
        """Apply a stored plan, verify every service, and restore unsuccessful interventions."""
        with self._lock():
            return self._apply_locked(incident_id, plan_id)

    def pending(self) -> list[dict[str, Any]]:
        """Find incomplete own transaction ledgers without changing configuration files."""
        root = self.target.root / ".opsresolve"
        if not root.exists():
            return []
        result = []
        allowed = {binding.file for binding in self.target.bindings if binding.repairable and not binding.sensitive}
        for path in list(root.glob("tx_*/transaction.json"))[:1000]:
            safe_file(self.target.root, path.relative_to(self.target.root).as_posix())
            if path.stat().st_size > 131072:
                raise ContractError("Transaction ledger exceeds its size limit")
            ledger = strict_json(path.read_bytes())
            if ledger.get("state") not in {"prepared", "manual_recovery"}:
                continue
            if any(item["file"] not in allowed for item in ledger["files"]):
                raise ContractError("Pending transaction exceeds current repair contracts")
            result.append({**ledger, "ledger_file": path.relative_to(self.target.root).as_posix()})
        return result

    def recover(self, apply: bool = False) -> list[dict[str, Any]]:
        """Review interrupted writes, then restore only bytes that still match this engine's patch."""
        with self._lock():
            results = []
            for ledger in self.pending():
                conflicts = []
                restored = []
                for item in ledger["files"]:
                    path = safe_file(self.target.root, item["file"])
                    current = digest(path.read_bytes())
                    if current == item["before_sha256"]:
                        continue
                    if current != item["after_sha256"]:
                        conflicts.append(item["file"])
                        continue
                    backup = safe_file(self.target.root, item["backup"])
                    original = backup.read_bytes()
                    if digest(original) != item["before_sha256"]:
                        conflicts.append(item["file"])
                        continue
                    if apply:
                        atomic_write(path, original, item["mode"])
                    restored.append(item["file"])
                result = {
                    "id": ledger["id"],
                    "state": "manual_recovery" if conflicts else "rolled_back",
                    "restored_files": restored,
                    "rollback_conflicts": conflicts,
                    "applied": apply,
                }
                if apply:
                    ledger["state"] = result["state"]
                    ledger_path = safe_file(self.target.root, ledger.pop("ledger_file"))
                    atomic_write(ledger_path, (canonical(ledger) + "\n").encode(), 0o600)
                    try:
                        record = self.journal.get(ledger["incident_id"])
                    except ContractError:
                        record = None
                    if record is not None:
                        record["state"] = result["state"]
                        record["repair"] = {**result, "checks": [], "created_at": timestamp()}
                        self.journal.append(record["id"], "interrupted_transaction_recovered", result)
                        self.journal.save(record)
                results.append(result)
            return results

    def _apply_locked(self, incident_id: str, plan_id: str) -> dict[str, Any]:
        record = self.journal.get(incident_id)
        result: dict[str, Any] = {
            "id": identifier("tx"),
            "state": "refused",
            "created_at": timestamp(),
            "plan_id": plan_id,
            "checks": [],
            "before_checks": [],
        }
        originals: dict[str, tuple[bytes, int]] = {}
        proposed: dict[str, bytes] = {}
        written: list[str] = []
        ledger: dict[str, Any] | None = None
        ledger_path: Path | None = None
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        try:
            plan = self._validate_plan(record, plan_id)
            if self.pending():
                raise ContractError("An interrupted transaction needs recovery before another repair")
            for change in plan["changes"]:
                grouped[change["file"]].append(change)
            for relative, changes in grouped.items():
                path = safe_file(self.target.root, relative)
                if path.stat().st_size > 1048576:
                    raise ContractError("Configuration file exceeded its size limit")
                original = path.read_bytes()
                if any(digest(original) != item["expected_sha256"] for item in changes):
                    raise ContractError(f"Stale configuration: {relative}; no files were changed")
                document = strict_json(original)
                for item in changes:
                    if not same_value(pointer_get(document, item["pointer"]), item["before"]):
                        raise ContractError(f"Stale field precondition: {relative}{item['pointer']}")
                    pointer_set(document, item["pointer"], item["after"])
                proposed[relative] = (canonical(document) + "\n").encode()
                if len(proposed[relative]) > 1048576:
                    raise ContractError("Proposed configuration exceeds 1 MiB")
                originals[relative] = (original, stat.S_IMODE(path.stat().st_mode))
            executor = ProbeExecutor(self.target)
            entry = next(item for item in self.target.services if item.id == self.target.entry)
            before = executor.run(Probe(f"http/{entry.id}", "http", entry.id, entry.cost))
            result["before_checks"].append(before.to_dict())
            if before.outcome == "ok":
                raise ContractError("Entry endpoint has already recovered; investigate before changing files")
            backup_root = self.target.root / ".opsresolve" / result["id"]
            backup_root.mkdir(mode=0o700)
            ledger = {"id": result["id"], "incident_id": incident_id, "state": "prepared", "files": []}
            for index, (relative, (original, mode)) in enumerate(originals.items()):
                backup = backup_root / f"{index}.json"
                atomic_write(backup, original, 0o600)
                ledger["files"].append(
                    {
                        "file": relative,
                        "backup": backup.relative_to(self.target.root).as_posix(),
                        "mode": mode,
                        "before_sha256": digest(original),
                        "after_sha256": digest(proposed[relative]),
                    }
                )
            ledger_path = backup_root / "transaction.json"
            atomic_write(ledger_path, (canonical(ledger) + "\n").encode(), 0o600)
            result["backup_directory"] = backup_root.relative_to(self.target.root).as_posix()
            for relative, (original, mode) in originals.items():
                path = safe_file(self.target.root, relative)
                if digest(path.read_bytes()) != digest(original):
                    raise ContractError(f"Configuration changed before write: {relative}")
                atomic_write(path, proposed[relative], mode)
                written.append(relative)
            result["state"] = "validating"
            self.journal.append(incident_id, "repair_applied", {"transaction_id": result["id"], "files": written})
            record["state"] = "validating"
            record["repair"] = result
            self.journal.save(record)
            all_healthy = True
            for round_number in (1, 2):
                if round_number == 2:
                    time.sleep(0.1)
                for service in self.target.services:
                    observation = executor.run(Probe(f"http/{service.id}", "http", service.id, service.cost))
                    check = {**observation.to_dict(), "round": round_number}
                    result["checks"].append(check)
                    self.journal.append(incident_id, "recovery_check", check)
                    all_healthy = all_healthy and observation.outcome == "ok"
            if not all_healthy:
                raise ContractError("At least one business endpoint failed recovery validation")
            result["state"] = "verified"
        except Exception as exc:
            result["error"] = str(exc)[:500]
            if written:
                conflicts = []
                for relative in reversed(written):
                    try:
                        path = safe_file(self.target.root, relative)
                        if digest(path.read_bytes()) != digest(proposed[relative]):
                            conflicts.append(relative)
                            continue
                        original, mode = originals[relative]
                        atomic_write(path, original, mode)
                    except (OSError, ContractError):
                        conflicts.append(relative)
                result["state"] = "manual_recovery" if conflicts else "rolled_back"
                result["rollback_conflicts"] = conflicts
                result["restored_files"] = [item for item in written if item not in conflicts]
            else:
                result["state"] = "refused"
        result["completed_at"] = timestamp()
        if ledger is not None and ledger_path is not None:
            ledger["state"] = result["state"]
            atomic_write(ledger_path, (canonical(ledger) + "\n").encode(), 0o600)
        record["repair"] = result
        record["state"] = result["state"]
        self.journal.append(incident_id, "repair_finished", result)
        self.journal.save(record)
        return result
