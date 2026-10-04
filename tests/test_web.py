"""Exercise browser-facing workflows and their local authorization boundary."""

import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from opsresolve.web import create_app


def ready(client: TestClient) -> dict[str, str]:
    assert client.get("/").status_code == 200
    bootstrap = client.get("/api/bootstrap").json()
    return {"x-opsresolve-csrf": bootstrap["csrf"]}


def wait(client: TestClient, incident_id: str, states: set[str]) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        record: dict[str, Any] = client.get(f"/api/incidents/{incident_id}").json()
        if record["state"] in states and (record["state"] != "diagnosed" or record.get("plan")):
            return record
        time.sleep(0.03)
    raise AssertionError("Workflow did not complete")


def test_complete_web_demo_and_report(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, demo=True), base_url="http://127.0.0.1") as client:
        headers = ready(client)
        target = client.get("/api/targets").json()[0]
        response = client.post(f"/api/targets/{target['id']}/investigations", headers=headers, json={"budget": 8})
        assert response.status_code == 202
        key = response.json()["incident_id"]
        record = wait(client, key, {"diagnosed"})
        assert len(record["plan"]["changes"]) == 2
        assert record["event_chain_intact"]
        assert client.get("/api/lab/traces").json()["origins"]
        response = client.post(f"/api/incidents/{key}/repair", headers=headers, json={"plan_id": record["plan"]["id"]})
        assert response.status_code == 202
        recovered = wait(client, key, {"verified"})
        assert len(recovered["repair"]["checks"]) == 10
        assert "verified" in client.get(f"/api/incidents/{key}/report").text


def test_rebinding_origin_and_csrf_are_refused(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        assert client.get("/api/targets").status_code == 401
        headers = ready(client)
        assert client.get("/", headers={"host": "attacker.example"}).status_code == 403
        value = {"url": "http://127.0.0.1:12345/"}
        assert client.post("/api/targets", json=value).status_code == 403
        assert (
            client.post(
                "/api/targets",
                headers={**headers, "origin": "https://attacker.example"},
                json=value,
            ).status_code
            == 403
        )
        assert client.post("/api/targets", headers=headers, json=value).status_code == 200
        assert client.get("/assets/unknown").status_code == 404


def test_invalid_budget_is_actionable(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        headers = ready(client)
        target = client.post("/api/targets", headers=headers, json={"url": "http://127.0.0.1:12345/"}).json()
        assert (
            client.post(
                f"/api/targets/{target['id']}/investigations",
                headers=headers,
                json={"budget": "bad"},
            ).status_code
            == 400
        )
