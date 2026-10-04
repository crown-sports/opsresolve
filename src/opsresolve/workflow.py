"""Cancellable investigation shared by command-line and browser controllers."""

from __future__ import annotations

import math
import threading
import time
from typing import Any

from .diagnosis import DiagnosisModel
from .domain import ContractError, Observation, Target, identifier, timestamp
from .journal import Journal
from .probes import ProbeExecutor


class Investigation:
    """Coordinate actual probes, model updates, budgets, and persistent progress."""

    def __init__(self, target: Target, journal: Journal, target_id: str = "cli"):
        self.target = target
        self.journal = journal
        self.target_id = target_id
        self.cancelled = threading.Event()

    def create(self, budget: float = 8, max_faults: int = 2, policy: str = "active") -> str:
        """Allocate a reviewable incident before asynchronous execution begins."""
        if (
            isinstance(budget, bool)
            or not isinstance(budget, (int, float))
            or not math.isfinite(budget)
            or not 0.01 <= budget <= 200
            or policy not in {"active", "all", "fixed"}
        ):
            raise ContractError("Invalid budget or investigation policy")
        DiagnosisModel(self.target, max_faults)
        key = identifier("inc")
        self.journal.create(
            {
                "id": key,
                "created_at": timestamp(),
                "target_name": self.target.name,
                "target_id": self.target_id,
                "state": "queued",
                "budget": budget,
                "spent": 0,
                "max_faults": max_faults,
                "policy": policy,
                "observations": [],
                "steps": [],
                "target": self.target.to_dict(),
            }
        )
        self.journal.append(key, "created", {"budget": budget, "max_faults": max_faults, "policy": policy})
        return key

    def run(self, incident_id: str) -> dict[str, Any]:
        """Investigate from the failing business endpoint; stop without guessing when evidence runs out."""
        record = self.journal.get(incident_id)
        if record["state"] != "queued":
            raise ContractError("An investigation can run only once")
        model = DiagnosisModel(self.target, record["max_faults"])
        executor = ProbeExecutor(self.target)
        before = time.perf_counter()
        record["state"] = "probing"
        self.journal.save(record)
        spent = 0.0
        reason = "no_informative_probe"
        initial = f"http/{self.target.entry}"
        ordered = [initial] + [key for key in model.probes if key != initial]
        if record["policy"] == "fixed":
            ordered = [initial] + sorted(
                (key for key in model.probes if key != initial),
                key=lambda key: (
                    0 if key.startswith("config/") else 1 if key.startswith("http/") else 2,
                    key,
                ),
            )
        try:
            while True:
                if self.cancelled.is_set():
                    reason = "cancelled"
                    break
                remaining = record["budget"] - spent
                gain = 0.0
                if not model.observed:
                    probe = model.probes[initial] if model.probes[initial].cost <= remaining else None
                elif record["policy"] in {"all", "fixed"}:
                    probe = next(
                        (
                            model.probes[key]
                            for key in ordered
                            if key not in model.observed
                            and model.probes[key].cost <= remaining + 1e-9
                            and (
                                record["policy"] == "all"
                                or len({model.predict(world, model.probes[key]) for world in model.worlds}) > 1
                            )
                        ),
                        None,
                    )
                else:
                    choice = model.choose(remaining)
                    probe = choice.probe if choice else None
                    gain = choice.information_bits if choice else 0
                if probe is None:
                    reason = "budget_exhausted" if model.choose(200) else "no_informative_probe"
                    break
                self.journal.append(
                    incident_id,
                    "probe_started",
                    {"probe_id": probe.id, "cost": probe.cost, "predicted_information_bits": gain},
                )
                observation = executor.run(probe)
                previous = len(model.worlds)
                model.observe(observation)
                spent += probe.cost
                step = {
                    "probe_id": probe.id,
                    "cost": probe.cost,
                    "information_bits": round(gain, 6),
                    "worlds_before": previous,
                    "worlds_after": len(model.worlds),
                    "outcome": observation.outcome,
                    "evidence_id": observation.id,
                    "duration_ms": observation.duration_ms,
                }
                record["observations"].append(observation.to_dict())
                record["steps"].append(step)
                record["spent"] = round(spent, 6)
                record["diagnosis"] = model.report("investigating", spent, record["budget"])
                self.journal.append(
                    incident_id,
                    "probe_finished",
                    {"step": step, "observation": observation.to_dict()},
                )
                self.journal.save(record)
                if not model.worlds:
                    reason = "model_conflict"
                    break
            record["diagnosis"] = model.report(reason, spent, record["budget"])
            record["state"] = "cancelled" if reason == "cancelled" else record["diagnosis"]["state"]
            record["duration_ms"] = round((time.perf_counter() - before) * 1000, 3)
            record["completed_at"] = timestamp()
            self.journal.append(
                incident_id,
                "investigation_finished",
                {"state": record["state"], "diagnosis": record["diagnosis"]},
            )
            self.journal.save(record)
            return record
        except Exception as exc:
            record["state"] = "failed"
            record["error"] = str(exc)[:500]
            self.journal.append(incident_id, "failed", {"error": record["error"]})
            self.journal.save(record)
            raise


def observations(record: dict[str, Any]) -> list[Observation]:
    """Recover typed evidence from a persisted incident snapshot."""
    return [Observation.from_dict(value) for value in record["observations"]]


def markdown_report(record: dict[str, Any]) -> str:
    """Render a portable incident report with evidence, precise scope, and recovery outcome."""
    diagnosis = record.get("diagnosis", {})
    lines = [
        f"# Incident: {record['target_name']}",
        "",
        f"ID: `{record['id']}`",
        f"State: **{record['state']}**",
        f"Created (UTC): {record['created_at']}",
        "",
        f"Probe cost: {record['spent']} / {record['budget']} declared units.",
        f"Investigation duration: {record.get('duration_ms', 0)} ms.",
        "",
        "## Explanations",
        "",
    ]
    for index, world in enumerate(diagnosis.get("explanations", []), 1):
        lines.append(f"{index}. " + (", ".join(f"`{item}`" for item in world) or "No modeled fault"))
    if not diagnosis.get("explanations"):
        lines.append("No consistent diagnosis; collect more evidence or update the model.")
    lines.extend(["", diagnosis.get("model_note", ""), "", "## Evidence", ""])
    for item in record["observations"]:
        facts = item["facts"]
        lines.append(f"- `{item['id']}` · `{item['probe_id']}` · **{item['outcome']}** · {item['duration_ms']} ms")
        lines.append(f"  `{facts.get('quote', facts.get('url', facts.get('error', '')))}`")
        if facts.get("status"):
            lines.append(f"  HTTP {facts['status']}; body: {facts.get('body', '')[:500]}")
    if record.get("plan"):
        lines.extend(["", "## Proposed configuration changes", ""])
        for change in record["plan"]["changes"]:
            lines.append(
                f"- `{change['file']}{change['pointer']}`: `{change['before']}` → `{change['after']}`; "
                f"evidence `{change['evidence_id']}`"
            )
    if record.get("repair"):
        lines.extend(["", "## Recovery", "", f"Transaction state: **{record['repair']['state']}**", ""])
        for check in record["repair"].get("checks", []):
            lines.append(
                f"- Round {check['round']}, `{check['probe_id']}`: {check['outcome']}, "
                f"HTTP {check['facts'].get('status', 'n/a')}"
            )
    lines.extend(
        [
            "",
            "Integrity hashes are not signatures. A working check does not establish absence "
            "of every possible production fault.",
            "",
        ]
    )
    return "\n".join(lines)
