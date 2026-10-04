"""Own isolated service processes, runtime fault injection, and deterministic restoration."""

from __future__ import annotations

import random
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from .domain import ContractError, Target, canonical, pointer_set, strict_json


class FaultLab:
    """A real application fixture; fault labels are private to injection and evaluation."""

    def __init__(
        self,
        base: Path | None = None,
        topology: str = "fanout",
        seed: int = 0,
        opaque_names: bool = False,
    ):
        """Create a new owned workspace and bounded HTTP dependency graph."""
        if topology not in {"fanout", "chain", "diamond"}:
            raise ContractError("Unknown lab topology")
        if base:
            base.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="opsresolve-lab-", dir=base))
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.configs: dict[str, bytes] = {}
        self.faults: list[str] = []
        self.topology = topology
        self.closed = False
        labels = ["gateway", "api", "catalog", "orders", "ledger"]
        rng = random.Random(seed)
        ids = [f"svc_{rng.randrange(10**7):07d}" for _ in labels] if opaque_names else labels
        self.ids = ids
        names = dict(zip(ids, labels, strict=True))
        structures = {
            "fanout": [(0, 1), (1, 2), (1, 3), (3, 4)],
            "chain": [(0, 1), (1, 3), (3, 2), (2, 4)],
            "diamond": [(0, 1), (1, 2), (1, 3), (2, 4), (3, 4)],
        }
        edges = [(ids[a], ids[b]) for a, b in structures[topology]]
        sockets = []
        ports = {}
        for service in ids:
            reservation = socket.socket()
            reservation.bind(("127.0.0.1", 0))
            sockets.append(reservation)
            ports[service] = reservation.getsockname()[1]
        urls = {key: f"http://127.0.0.1:{ports[key]}/business/{key}" for key in ids}
        (self.root / "config").mkdir()
        (self.root / "storage").mkdir()
        bindings = []
        self.route_bindings: list[str] = []
        self.database_bindings: list[str] = []
        for service in ids:
            children = [b for a, b in edges if a == service]
            document = {
                "service": service,
                "port": ports[service],
                "path": f"/business/{service}",
                "upstreams": {child: urls[child] for child in children},
            }
            for child in children:
                binding_id = f"route_{service}_{child}"
                self.route_bindings.append(binding_id)
                bindings.append(
                    {
                        "id": binding_id,
                        "service": service,
                        "file": f"config/{service}.json",
                        "pointer": f"/upstreams/{child}",
                        "expected": {"url_of": child},
                        "repairable": True,
                        "reload": "hot",
                    }
                )
            if not children:
                database_name = f"storage/{service}.sqlite3"
                with sqlite3.connect(self.root / database_name) as connection:
                    connection.execute("CREATE TABLE inventory(name TEXT PRIMARY KEY, quantity INTEGER)")
                    connection.executemany("INSERT INTO inventory VALUES(?,?)", [("books", 12), ("pens", 40)])
                document["database"] = database_name
                binding_id = f"database_{service}"
                self.database_bindings.append(binding_id)
                bindings.append(
                    {
                        "id": binding_id,
                        "service": service,
                        "file": f"config/{service}.json",
                        "pointer": "/database",
                        "expected": database_name,
                        "repairable": True,
                        "reload": "hot",
                    }
                )
            content = (canonical(document) + "\n").encode()
            self.configs[service] = content
            (self.root / f"config/{service}.json").write_bytes(content)
        manifest = {
            "version": 1,
            "name": "Storefront recovery lab",
            "entry": ids[0],
            "services": [
                {
                    "id": key,
                    "name": key if opaque_names else names[key].title(),
                    "url": urls[key],
                    "health_url": f"http://127.0.0.1:{ports[key]}/health",
                    "body_contains": '"ready": true',
                    "timeout_seconds": 2.0,
                }
                for key in ids
            ],
            "dependencies": [{"source": a, "target": b} for a, b in edges],
            "bindings": bindings,
        }
        self.target = Target.from_dict(manifest, self.root)
        self.manifest = self.root / "target.json"
        self.manifest.write_text(canonical(manifest) + "\n")
        for reservation in sockets:
            reservation.close()

    def start(self) -> FaultLab:
        """Start one OS process per service and wait for actual liveness responses."""
        try:
            for service in self.ids:
                self._start_service(service)
            return self
        except Exception:
            self.close()
            raise

    def _start_service(self, service: str) -> None:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "opsresolve.lab_worker",
                "--config",
                str(self.root / f"config/{service}.json"),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes[service] = process
        health = next(item.health_url for item in self.target.services if item.id == service)
        if health is None:
            raise ContractError("Lab has no liveness URL")
        deadline = time.monotonic() + 8
        opener = build_opener(ProxyHandler({}))
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ContractError("Lab service failed to start")
            try:
                with opener.open(health, timeout=0.2) as response:
                    if response.code == 200:
                        return
            except (URLError, OSError):
                time.sleep(0.03)
        raise ContractError("Lab service did not become live")

    def _stop_service(self, service: str) -> None:
        process = self.processes.pop(service, None)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def reset(self) -> None:
        """Restore exact healthy configuration and restart only owned stopped service processes."""
        self.faults = []
        for service, content in self.configs.items():
            (self.root / f"config/{service}.json").write_bytes(content)
            if service not in self.processes or self.processes[service].poll() is not None:
                self._start_service(service)

    def inject(self, specifications: list[tuple[str, str]]) -> list[str]:
        """Introduce real route, database, local-code, or process failures and return evaluator truth."""
        self.reset()
        fault_ids = []
        for kind, subject in specifications:
            if kind in {"route_path", "route_port", "database"}:
                binding = next((item for item in self.target.bindings if item.id == subject), None)
                if binding is None:
                    raise ContractError("Unknown lab binding")
                path = self.root / binding.file
                document = strict_json(path.read_bytes())
                expected = self.target.expected_value(binding)
                if kind == "route_path":
                    replacement = expected + "/missing"
                elif kind == "route_port":
                    reservation = socket.socket()
                    reservation.bind(("127.0.0.1", 0))
                    replacement = f"http://127.0.0.1:{reservation.getsockname()[1]}/missing"
                    reservation.close()
                else:
                    replacement = "storage/missing.sqlite3"
                pointer_set(document, binding.pointer, replacement)
                path.write_text(canonical(document) + "\n")
                fault_ids.append(f"config/{binding.id}")
            elif kind == "application":
                if subject not in self.ids:
                    raise ContractError("Unknown lab service")
                path = self.root / f"config/{subject}.json"
                document = strict_json(path.read_bytes())
                document["application_failure"] = True
                path.write_text(canonical(document) + "\n")
                fault_ids.append(f"local_failure/{subject}")
            elif kind == "unavailable":
                if subject not in self.ids:
                    raise ContractError("Unknown lab service")
                self._stop_service(subject)
                fault_ids.append(f"unavailable/{subject}")
            else:
                raise ContractError("Unknown lab fault kind")
        self.faults = sorted(fault_ids)
        return self.faults

    def scenarios(self) -> list[dict[str, Any]]:
        """Expose named product demos without inserting truth labels into the target manifest."""
        return [
            {
                "id": "hidden_pair",
                "title": "Two faults hidden behind one 503",
                "description": "A wrong upstream route conceals a database configuration failure.",
                "specifications": [
                    ("route_path", self.route_bindings[0]),
                    ("database", self.database_bindings[0]),
                ],
            },
            {
                "id": "wrong_port",
                "title": "A persistent routing error",
                "description": "Restarting processes leaves the wrong upstream port unchanged.",
                "specifications": [("route_port", self.route_bindings[1])],
            },
            {
                "id": "branch_pair",
                "title": "Failures in two dependency branches",
                "description": "Independent bad routes require two precise corrections.",
                "specifications": [
                    ("route_path", self.route_bindings[-1]),
                    ("database", self.database_bindings[0]),
                ],
            },
            {
                "id": "process_down",
                "title": "An unavailable dependency",
                "description": "Endpoint checks isolate the dependency; process restart requires an operator.",
                "specifications": [("unavailable", self.ids[-1])],
            },
            {
                "id": "healthy",
                "title": "Healthy application",
                "description": "Every declared business request succeeds.",
                "specifications": [],
            },
        ]

    def scenario(self, key: str) -> None:
        """Inject only a predefined owned fixture scenario from a browser action."""
        scenario = next((item for item in self.scenarios() if item["id"] == key), None)
        if scenario is None:
            raise ContractError("Unknown lab scenario")
        self.inject(scenario["specifications"])

    def restart(self) -> None:
        """Restart owned processes while preserving persisted faulty configuration for comparison."""
        for service in self.ids:
            self._stop_service(service)
            self._start_service(service)

    def export_traces(self) -> Any:
        """Read real recorded HTTP and database spans, without manufacturing a call history."""
        from .traces import load_otlp

        return load_otlp(self.root / "traces.ndjson")

    def close(self, remove: bool = True) -> None:
        """Stop only processes created by this fixture and optionally remove its owned workspace."""
        if self.closed:
            return
        for service in list(self.processes):
            self._stop_service(service)
        if remove:
            shutil.rmtree(self.root)
        self.closed = True

    def __enter__(self) -> FaultLab:
        return self.start()

    def __exit__(self, *args: Any) -> None:
        self.close()
