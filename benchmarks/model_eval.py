"""Evaluate optional report explanations on captured diagnoses; do not call this model-only RCA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run import source_digest

from opsresolve.advisor import OllamaModel, explain, explanation_input
from opsresolve.domain import canonical, strict_json, timestamp


def main() -> None:
    """Keep the full denominator, rejected outputs, prompts, and observed model latency."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8766")
    parser.add_argument("--model", default="local-qwen")
    parser.add_argument("--limit", type=int, default=18)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    selected = [
        item
        for item in (strict_json(line) for line in args.records.read_text().splitlines())
        if item["policy"] == "active" and item["record"].get("diagnosis", {}).get("state") == "diagnosed"
    ]
    selected = selected[:: max(1, len(selected) // args.limit)][: args.limit]
    rows = []
    for item in selected:
        record = item["record"]
        system, user = explanation_input(record)
        result = explain(OllamaModel(args.endpoint, args.model), record)
        row = {
            "case": item["case"],
            "system": system,
            "user": user,
            "result": result,
            "diagnosis_provided_to_model": True,
        }
        rows.append(row)
        with (args.output / "rows.jsonl").open("a") as stream:
            stream.write(canonical(row) + "\n")
        print(
            item["case"],
            result["state"],
            result.get("error", ""),
            result["duration_ms"],
            flush=True,
        )
    report = {
        "generated_at": timestamp(),
        "source_digest": source_digest(),
        "model": args.model,
        "cases": len(rows),
        "accepted_explanations": sum(row["result"]["state"] == "accepted" for row in rows),
        "rejected_explanations": sum(row["result"]["state"] == "rejected" for row in rows),
        "scope": (
            "Model receives algorithm-derived faults. Acceptance checks identifiers and exact "
            "evidence references, not semantic truth of prose or model-only diagnosis accuracy."
        ),
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
