"""Paired live-process experiments; labels never enter the target, probes, or planner."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
from pathlib import Path

from opsresolve.domain import Probe, canonical, timestamp
from opsresolve.journal import Journal
from opsresolve.lab import FaultLab
from opsresolve.probes import ProbeExecutor
from opsresolve.repair import RepairTransaction
from opsresolve.traces import analyze_traces
from opsresolve.workflow import Investigation


def source_digest() -> str:
    """Fingerprint core code, UI assets, and the evaluation harness independently of report files."""
    root = Path(__file__).resolve().parents[1]
    sha = hashlib.sha256()
    paths = (
        list((root / "src").rglob("*.py"))
        + list((root / "src").rglob("*.js"))
        + list((root / "src").rglob("*.css"))
        + list((root / "src").rglob("*.html"))
        + list((root / "benchmarks").glob("*.py"))
    )
    for path in sorted(paths):
        sha.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return sha.hexdigest()


def cases(lab: FaultLab) -> list[list[tuple[str, str]]]:
    """Cover every declared configuration contract, manual faults, and four simultaneous pairs."""
    singles = [("route_port" if index % 2 else "route_path", key) for index, key in enumerate(lab.route_bindings)]
    singles += [("database", key) for key in lab.database_bindings]
    pairs = [
        [("route_path", lab.route_bindings[0]), ("database", lab.database_bindings[0])],
        [("route_port", lab.route_bindings[1]), ("route_path", lab.route_bindings[-1])],
        [("route_path", lab.route_bindings[2]), ("database", lab.database_bindings[0])],
        [("route_port", lab.route_bindings[0]), ("database", lab.database_bindings[-1])],
    ]
    manual = [[(kind, service)] for kind in ("application", "unavailable") for service in (lab.ids[-1], lab.ids[1])]
    return [[]] + [[item] for item in singles] + manual + pairs


def main() -> None:
    """Record every incident, plan, true runtime recovery, and comparison cost denominator."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=90421)
    parser.add_argument("--budget", type=float, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    journal = Journal(args.output / "private-journal.sqlite3")
    rows = []
    records = []
    restart_rows = []
    for topology_index, topology in enumerate(("fanout", "chain", "diamond")):
        with FaultLab(topology=topology, seed=args.seed + topology_index, opaque_names=True) as lab:
            for index, specifications in enumerate(cases(lab)):
                truth = lab.inject(specifications)
                case_id = f"{topology}-{index:02d}"
                full_cost = sum(service.cost * 2 for service in lab.target.services) + sum(
                    binding.cost for binding in lab.target.bindings
                )
                case_records = []
                for policy, budget in (
                    ("all", full_cost),
                    ("fixed", args.budget),
                    ("active", args.budget),
                ):
                    job = Investigation(lab.target, journal)
                    key = job.create(budget=budget, policy=policy)
                    record = job.run(key)
                    exact = record["diagnosis"]["explanations"] == [truth]
                    transaction = RepairTransaction(lab.target, journal)
                    plan = transaction.prepare(key)
                    row = {
                        "case": case_id,
                        "topology": topology,
                        "policy": policy,
                        "truth": truth,
                        "state": record["state"],
                        "exact": exact,
                        "cost": record["spent"],
                        "full_cost": full_cost,
                        "probes": len(record["steps"]),
                        "duration_ms": record["duration_ms"],
                        "plan_changes": len(plan["changes"]),
                        "repair_state": "not_applied",
                    }
                    case_records.append((row, record, plan))
                active_row, active_record, active_plan = case_records[-1]
                if active_plan["can_apply"]:
                    actual = RepairTransaction(lab.target, journal).apply(active_record["id"], active_plan["id"])
                    active_row["repair_state"] = actual["state"]
                    active_row["recovery_checks"] = len(actual["checks"])
                    active_row["passing_recovery_checks"] = sum(item["outcome"] == "ok" for item in actual["checks"])
                    active_record = journal.get(active_record["id"])
                for row, record, plan in case_records:
                    rows.append(row)
                    records.append(
                        {
                            "case": case_id,
                            "policy": row["policy"],
                            "record": active_record if row["policy"] == "active" else {**record, "plan": plan},
                        }
                    )
                trace_report = analyze_traces(lab.export_traces())
                (args.output / f"{case_id}-traces.json").write_text(canonical(trace_report) + "\n")
                if (
                    specifications
                    and all(kind in {"route_path", "route_port", "database"} for kind, _ in specifications)
                    and index <= 3
                ):
                    lab.inject(specifications)
                    lab.restart()
                    service = next(item for item in lab.target.services if item.id == lab.target.entry)
                    after_restart = ProbeExecutor(lab.target).run(
                        Probe(f"http/{service.id}", "http", service.id, service.cost)
                    )
                    restart_rows.append(
                        {
                            "case": case_id,
                            "outcome": after_restart.outcome,
                            "status": after_restart.facts.get("status"),
                        }
                    )
                print(
                    case_id,
                    "exact",
                    active_row["exact"],
                    "cost",
                    active_row["cost"],
                    "repair",
                    active_row["repair_state"],
                    flush=True,
                )
    summary = {}
    for policy in ("all", "fixed", "active"):
        subset = [row for row in rows if row["policy"] == policy]
        summary[policy] = {
            "cases": len(subset),
            "exact_diagnoses": sum(row["exact"] for row in subset),
            "mean_cost": statistics.mean(row["cost"] for row in subset),
            "mean_probes": statistics.mean(row["probes"] for row in subset),
            "median_duration_ms": statistics.median(row["duration_ms"] for row in subset),
            "budget_violations": sum(
                row["cost"] > (row["full_cost"] if policy == "all" else args.budget) + 1e-8 for row in subset
            ),
        }
    repairs = [row for row in rows if row["policy"] == "active" and row["repair_state"] != "not_applied"]
    report = {
        "generated_at": timestamp(),
        "seed": args.seed,
        "budget": args.budget,
        "source_digest": source_digest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "machine": platform.machine(),
        },
        "summary": summary,
        "repairable_incidents": len(repairs),
        "verified_recoveries": sum(row["repair_state"] == "verified" for row in repairs),
        "recovery_checks": sum(row["recovery_checks"] for row in repairs),
        "restart_comparison": restart_rows,
        "scope": "Own deterministic live-process development fixtures; not a production corpus or RCAEval evaluation",
    }
    (args.output / "rows.jsonl").write_text("\n".join(canonical(row) for row in rows) + "\n")
    (args.output / "records.jsonl").write_text("\n".join(canonical(record) for record in records) + "\n")
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
