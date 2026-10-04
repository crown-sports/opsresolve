"""Model interpretations cannot replace diagnosed faults or fabricate evidence quotes."""

from typing import Any

import pytest

from opsresolve.advisor import explain, validate_explanation
from opsresolve.domain import ContractError, canonical


def record() -> dict[str, Any]:
    return {
        "target_name": "Test",
        "diagnosis": {
            "state": "diagnosed",
            "explanation_count": 1,
            "explanations": [["config/route"]],
            "faults": [{"id": "config/route", "evidence_ids": ["ev_route"]}],
        },
        "observations": [
            {
                "id": "ev_route",
                "probe_id": "config/route",
                "outcome": "drift",
                "facts": {"quote": "current port 8000; expected port 8001"},
            }
        ],
    }


def answer() -> dict[str, Any]:
    return {
        "summary": "Correct the observed routing setting.",
        "findings": [
            {
                "fault_id": "config/route",
                "explanation": "The configured port differs from intent.",
                "evidence_id": "ev_route",
                "quote": "current port 8000",
            }
        ],
    }


def test_valid_quote_and_fault_set() -> None:
    assert validate_explanation(canonical(answer()), record())["findings"][0]["fault_id"] == "config/route"


@pytest.mark.parametrize(
    "field,value",
    [
        ("fault_id", "local_failure/server"),
        ("evidence_id", "ev_invented"),
        ("quote", "current port 9999"),
    ],
)
def test_fabricated_findings_are_rejected(field: str, value: str) -> None:
    value_object = answer()
    value_object["findings"][0][field] = value
    with pytest.raises(ContractError):
        validate_explanation(canonical(value_object), record())


def test_model_failure_is_visible_without_changing_control_state() -> None:
    class BrokenModel:
        def complete(self, system: str, user: str) -> str:
            raise OSError("Local model unavailable")

    captured = record()
    result = explain(BrokenModel(), captured)
    assert result["state"] == "rejected"
    assert captured["diagnosis"]["explanations"] == [["config/route"]]
