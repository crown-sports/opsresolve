"""Human-facing commands for setup, investigation, recovery, and the real service lab."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any

from .advisor import OllamaModel, explain
from .domain import ContractError, Target, canonical
from .journal import Journal
from .lab import FaultLab
from .repair import RepairTransaction
from .trace_compare import compare_traces, comparison_markdown
from .traces import analyze_traces, load_otlp, trace_markdown
from .workflow import Investigation, markdown_report


def default_state() -> Path:
    """Keep private incident data outside source repositories by default."""
    return Path.home() / ".opsresolve"


def display(record: dict[str, Any]) -> None:
    """Print outcome, concrete causes, and a usable next action before implementation details."""
    print(f"{record['target_name']}: {record['state']}")
    print(f"Incident: {record['id']}")
    print(f"Checks: {len(record['observations'])}; cost {record['spent']}/{record['budget']}")
    for index, world in enumerate(record.get("diagnosis", {}).get("explanations", []), 1):
        print(f"Explanation {index}: {', '.join(world) or 'healthy'}")
    plan = record.get("plan", {})
    for change in plan.get("changes", []):
        print(
            f"Change {change['file']}{change['pointer']}: {canonical(change['before'])} -> {canonical(change['after'])}"
        )
    for message in plan.get("blocked", []):
        print(f"Operator action: {message}")
    if record.get("repair"):
        print(f"Recovery: {record['repair']['state']} ({len(record['repair']['checks'])} business checks)")


def check_output_path(output: Path, protected: tuple[Path, ...]) -> None:
    """Refuse aliases of source files or the incident journal before doing any work."""
    for source in protected:
        if output.resolve() == source.resolve() or (output.exists() and source.exists() and output.samefile(source)):
            raise ContractError("Output must not overwrite an input file or the incident journal; choose another path")


def write_output(output: Path, content: str) -> None:
    """Allow a new report folder and consistently encode portable text exports."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def main() -> int:
    """Run the same bounded workflows available through the browser workbench."""
    parser = argparse.ArgumentParser(prog="opsresolve", description="Investigate service failures and verify recovery")
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="Create a URL triage manifest")
    initialize.add_argument("--url", required=True)
    initialize.add_argument("--name", default="My service")
    initialize.add_argument("--output", type=Path, default=Path("target.json"))
    diagnose = commands.add_parser("diagnose", help="Investigate a declared application")
    diagnose.add_argument("target", type=Path)
    diagnose.add_argument("--budget", type=float, default=8)
    diagnose.add_argument("--max-faults", type=int, choices=(1, 2, 3), default=2)
    diagnose.add_argument("--policy", choices=("active", "all", "fixed"), default="active")
    diagnose.add_argument("--state", type=Path, default=default_state())
    diagnose.add_argument("--report", type=Path)
    diagnose.add_argument("--model-url")
    diagnose.add_argument("--model", default="qwen3:4b")
    repair = commands.add_parser("repair", help="Review or apply a stored configuration plan")
    repair.add_argument("target", type=Path)
    repair.add_argument("--incident", required=True)
    repair.add_argument("--state", type=Path, default=default_state())
    repair.add_argument("--apply", action="store_true", help="Apply the reviewed, preconditioned plan")
    recover = commands.add_parser("recover", help="Review or restore interrupted configuration transactions")
    recover.add_argument("target", type=Path)
    recover.add_argument("--state", type=Path, default=default_state())
    recover.add_argument("--apply", action="store_true")
    demo = commands.add_parser("demo", help="Run and recover a real five-service failure")
    demo.add_argument("--no-repair", action="store_true")
    demo.add_argument("--state", type=Path, default=default_state())
    demo.add_argument("--report", type=Path)
    demo.add_argument("--model-url")
    demo.add_argument("--model", default="qwen3:4b")
    serve = commands.add_parser("serve", help="Open the local incident workbench")
    serve.add_argument("--demo", action="store_true")
    serve.add_argument("--target", type=Path, action="append", default=[])
    serve.add_argument("--state", type=Path, default=default_state())
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--allow-repair", action="store_true")
    serve.add_argument("--model-url")
    serve.add_argument("--model", default="qwen3:4b")
    report = commands.add_parser("report", help="Export an existing incident")
    report.add_argument("incident")
    report.add_argument("--state", type=Path, default=default_state())
    report.add_argument("--output", type=Path)
    report.add_argument("--format", choices=("markdown", "json"), default="markdown")
    trace = commands.add_parser("trace", help="Find recorded failure origins and latency in an OTLP export")
    trace.add_argument("input", type=Path)
    trace.add_argument("--output", type=Path)
    trace.add_argument("--format", choices=("markdown", "json"), default="markdown")
    compare = commands.add_parser("trace-compare", help="Compare before/after OTLP exports for regressions")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument("--min-spans", type=int, default=5)
    compare.add_argument("--latency-increase-pct", type=float, default=20)
    compare.add_argument("--latency-increase-ms", type=float, default=10)
    compare.add_argument("--error-increase-pp", type=float, default=0)
    compare.add_argument("--output", type=Path)
    compare.add_argument("--format", choices=("markdown", "json"), default="markdown")
    compare.add_argument("--check", action="store_true", help="Exit 1 on regressions or insufficient evidence")
    model_server = commands.add_parser("model-serve", help="Run an optional local Hugging Face model")
    model_server.add_argument("--path", type=Path, required=True)
    model_server.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    model_server.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    try:
        output = getattr(args, "report", None) or getattr(args, "output", None)
        if output is not None:
            protected = tuple(
                value
                for name in ("target", "input", "before", "after")
                if isinstance(value := getattr(args, name, None), Path)
            )
            if hasattr(args, "state"):
                protected += (args.state / "incidents.sqlite3",)
            check_output_path(output, protected)
        if args.command == "init":
            manifest = {
                "version": 1,
                "name": args.name,
                "entry": "service",
                "services": [{"id": "service", "url": args.url}],
            }
            target = Target.from_dict(manifest, args.output.resolve().parent)
            if args.output.exists():
                raise ContractError("Output already exists; choose a new manifest path")
            write_output(args.output, canonical(target.to_dict()) + "\n")
            print(f"Created {args.output.resolve()}; run opsresolve diagnose {args.output}")
        elif args.command == "diagnose":
            target = Target.load(args.target)
            journal = Journal(args.state / "incidents.sqlite3")
            work = Investigation(target, journal)
            incident_id = work.create(args.budget, args.max_faults, args.policy)
            record = work.run(incident_id)
            RepairTransaction(target, journal).prepare(incident_id)
            record = journal.get(incident_id)
            if args.model_url:
                record["advisor"] = explain(OllamaModel(args.model_url, args.model), record)
                journal.save(record)
            display(record)
            if args.report:
                write_output(args.report, markdown_report(record))
            if record.get("plan", {}).get("can_apply"):
                print(
                    f"Review/apply: opsresolve repair {args.target} --incident {incident_id} "
                    f"--state {args.state} --apply"
                )
        elif args.command == "repair":
            target = Target.load(args.target)
            journal = Journal(args.state / "incidents.sqlite3")
            transaction = RepairTransaction(target, journal)
            record = journal.get(args.incident)
            plan = record.get("plan") or transaction.prepare(args.incident)
            if args.apply:
                transaction.apply(args.incident, plan["id"])
            display(journal.get(args.incident))
        elif args.command == "recover":
            target = Target.load(args.target)
            transaction = RepairTransaction(target, Journal(args.state / "incidents.sqlite3"))
            print(canonical(transaction.recover(args.apply)))
        elif args.command == "demo":
            with FaultLab() as lab:
                lab.scenario("hidden_pair")
                journal = Journal(args.state / "incidents.sqlite3")
                work = Investigation(lab.target, journal)
                incident_id = work.create()
                work.run(incident_id)
                transaction = RepairTransaction(lab.target, journal)
                plan = transaction.prepare(incident_id)
                if args.model_url:
                    record = journal.get(incident_id)
                    record["advisor"] = explain(OllamaModel(args.model_url, args.model), record)
                    journal.save(record)
                if not args.no_repair and plan["can_apply"]:
                    transaction.apply(incident_id, plan["id"])
                record = journal.get(incident_id)
                display(record)
                if args.report:
                    write_output(args.report, markdown_report(record))
        elif args.command == "serve":
            from .web import create_app

            uvicorn = importlib.import_module("uvicorn")
            model = OllamaModel(args.model_url, args.model) if args.model_url else None
            app = create_app(args.state, args.demo, tuple(args.target), args.allow_repair, model)
            print(f"Open http://127.0.0.1:{args.port} · Ctrl-C stops owned demo services")
            uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
        elif args.command == "report":
            record = Journal(args.state / "incidents.sqlite3").get(args.incident)
            content = canonical(record) if args.format == "json" else markdown_report(record)
            if args.output:
                write_output(args.output, content)
            else:
                print(content)
        elif args.command == "trace":
            analyzed = analyze_traces(load_otlp(args.input))
            content = canonical(analyzed) if args.format == "json" else trace_markdown(analyzed)
            if args.output:
                write_output(args.output, content)
            else:
                print(content)
        elif args.command == "trace-compare":
            comparison = compare_traces(
                load_otlp(args.before),
                load_otlp(args.after),
                min_spans=args.min_spans,
                latency_increase_pct=args.latency_increase_pct,
                latency_increase_ms=args.latency_increase_ms,
                error_increase_pp=args.error_increase_pp,
            )
            content = canonical(comparison) if args.format == "json" else comparison_markdown(comparison)
            if args.output:
                write_output(args.output, content)
            else:
                print(content)
            if args.check and comparison["state"] != "no_regression":
                return 1
        elif args.command == "model-serve":
            from .model_server import create_model_app

            uvicorn = importlib.import_module("uvicorn")
            uvicorn.run(
                create_model_app(args.path, args.device),
                host="127.0.0.1",
                port=args.port,
                log_level="warning",
            )
    except (ContractError, OSError, ImportError) as exc:
        print(f"OpsResolve: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
