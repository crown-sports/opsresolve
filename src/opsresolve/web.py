"""Loopback workbench controllers; every action uses the same audited domain workflow."""

from __future__ import annotations

import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from .advisor import ChatModel, explain
from .domain import ContractError, Target, canonical, digest, identifier
from .journal import Journal
from .lab import FaultLab
from .repair import RepairTransaction
from .traces import analyze_traces
from .workflow import Investigation, markdown_report


@dataclass
class Registration:
    id: str
    target: Target
    managed: bool
    lock: threading.Lock


def create_app(
    state: Path,
    demo: bool = False,
    target_paths: tuple[Path, ...] = (),
    allow_repair: bool = False,
    model: ChatModel | None = None,
) -> FastAPI:
    """Bind trusted host targets and optional owned fixtures to a single-operator local UI."""
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    journal = Journal(state / "incidents.sqlite3")
    registrations: dict[str, Registration] = {}
    jobs: dict[str, Investigation] = {}
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="opsresolve")
    session = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    lab: FaultLab | None = None
    ui = Path(__file__).parent / "ui"

    def register(target: Target, managed: bool = False) -> Registration:
        key = digest((canonical(target.to_dict()) + str(target.root)).encode())[:20]
        entry = Registration(key, target, managed, threading.Lock())
        registrations[key] = entry
        return entry

    for path in target_paths:
        register(Target.load(path))
    if demo:
        lab = FaultLab(state / "labs").start()
        lab.scenario("hidden_pair")
        register(lab.target, managed=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        try:
            yield
        finally:
            for job in jobs.values():
                job.cancelled.set()
            pool.shutdown(wait=True, cancel_futures=True)
            if lab:
                lab.close()

    app = FastAPI(title="OpsResolve", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.journal = journal
    app.state.registrations = registrations
    app.state.lab = lab

    @app.middleware("http")
    async def local_boundary(request: Request, call_next: Any) -> Response:
        """Reject rebinding hosts and cross-origin mutations before any diagnostic adapter runs."""
        try:
            host = urlsplit("http://" + request.headers.get("host", "")).hostname
        except ValueError:
            host = None
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"detail": "This workbench accepts loopback hosts only"}, 403)
        if request.url.path.startswith("/api/"):
            if not secrets.compare_digest(request.cookies.get("opsresolve_session", ""), session):
                return JSONResponse({"detail": "Open the workbench before using its API"}, 401)
            if request.method not in {"GET", "HEAD"}:
                origin = request.headers.get("origin")
                expected_origin = str(request.base_url).rstrip("/")
                if (origin is not None and origin != expected_origin) or not secrets.compare_digest(
                    request.headers.get("x-opsresolve-csrf", ""), csrf
                ):
                    return JSONResponse({"detail": "Cross-origin or unauthenticated action refused"}, 403)
                length = request.headers.get("content-length", "")
                limit = 5242880 if request.url.path == "/api/traces" else 131072
                if not length.isdecimal() or int(length) > limit:
                    return JSONResponse({"detail": "Request exceeds its capture limit"}, 413)
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ContractError)
    async def contract_error(request: Request, exc: ContractError) -> JSONResponse:
        """Present contract failures as usable operator feedback."""
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def target_for(key: str) -> Registration:
        entry = registrations.get(key)
        if not entry:
            raise HTTPException(404, "Target is not registered in this workbench session")
        return entry

    def incident_target(incident_id: str) -> Registration:
        record = journal.get(incident_id)
        return target_for(record["target_id"])

    def take(entry: Registration) -> None:
        if not entry.lock.acquire(blocking=False):
            raise HTTPException(409, "This target already has an active operation")

    @app.get("/")
    def index() -> Response:
        """Issue a local session cookie when the operator opens the workbench."""
        response = FileResponse(ui / "index.html")
        response.set_cookie("opsresolve_session", session, httponly=True, samesite="strict")
        return response

    @app.get("/assets/{name}")
    def asset(name: str) -> Response:
        """Serve only the two packaged UI assets, without filesystem path interpretation."""
        if name not in {"workbench.css", "workbench.js"}:
            raise HTTPException(404, "Unknown asset")
        return FileResponse(ui / name)

    @app.get("/api/bootstrap")
    def bootstrap() -> dict[str, Any]:
        """Expose product capabilities and a same-origin action token."""
        return {
            "csrf": csrf,
            "model_available": model is not None,
            "lab_available": lab is not None,
            "real_repair_enabled": allow_repair,
            "scenarios": [{key: item[key] for key in ("id", "title", "description")} for item in lab.scenarios()]
            if lab
            else [],
        }

    @app.get("/api/targets")
    def targets() -> list[dict[str, Any]]:
        """Show portable topology and scope, excluding host filesystem roots."""
        return [
            {
                "id": entry.id,
                "manifest": entry.target.to_dict(),
                "managed_lab": entry.managed,
                "busy": entry.lock.locked(),
                "repair_enabled": entry.managed or allow_repair,
            }
            for entry in registrations.values()
        ]

    @app.post("/api/targets")
    def add_target(value: dict[str, Any]) -> dict[str, Any]:
        """Register URL triage or a portable manifest within a new empty import workspace."""
        if len(registrations) >= 32:
            raise ContractError("This session already has 32 targets")
        manifest = value.get("manifest")
        if manifest is None:
            manifest = {
                "version": 1,
                "name": value.get("name", "My service"),
                "entry": "service",
                "services": [
                    {
                        "id": "service",
                        "url": value.get("url", ""),
                        "expected_status": value.get("expected_status", 200),
                    }
                ],
            }
        root = state / "imports" / identifier("target")
        root.mkdir(parents=True, mode=0o700)
        target = Target.from_dict(manifest, root)
        entry = register(target)
        return {"id": entry.id}

    @app.post("/api/targets/{key}/investigations", status_code=202)
    def investigate(key: str, value: dict[str, Any]) -> dict[str, Any]:
        """Start a bounded background investigation and stream progress through its journal."""
        entry = target_for(key)
        take(entry)
        try:
            job = Investigation(entry.target, journal, key)
            incident_id = job.create(value.get("budget", 8), value.get("max_faults", 2))
            jobs[incident_id] = job

            def execute() -> None:
                try:
                    job.run(incident_id)
                    RepairTransaction(entry.target, journal).prepare(incident_id)
                finally:
                    jobs.pop(incident_id, None)
                    entry.lock.release()

            pool.submit(execute)
            return {"incident_id": incident_id}
        except Exception:
            entry.lock.release()
            raise

    @app.get("/api/incidents")
    def incidents() -> list[dict[str, Any]]:
        """List persistent incident history independently of the current target session."""
        return journal.recent()

    @app.get("/api/incidents/{incident_id}")
    def incident(incident_id: str) -> dict[str, Any]:
        """Return evidence, candidate explanations, plans, and actual recovery checks."""
        return {**journal.get(incident_id), "event_chain_intact": journal.verify(incident_id)}

    @app.get("/api/incidents/{incident_id}/events")
    def events(incident_id: str) -> list[dict[str, Any]]:
        """Return the ordered investigation and transaction timeline."""
        journal.get(incident_id)
        return journal.events(incident_id)

    @app.post("/api/incidents/{incident_id}/cancel")
    def cancel(incident_id: str) -> dict[str, Any]:
        """Cancel between probes; a running network attempt finishes within its declared timeout."""
        job = jobs.get(incident_id)
        if not job:
            raise HTTPException(409, "Investigation is no longer running")
        job.cancelled.set()
        return {"state": "cancellation_requested"}

    @app.post("/api/incidents/{incident_id}/repair", status_code=202)
    def repair(incident_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Apply only a stored plan when the owner enabled repairs for this registered target."""
        entry = incident_target(incident_id)
        if not entry.managed and not allow_repair:
            raise HTTPException(
                403,
                "Real-target repairs are disabled; restart with --allow-repair to enable declared contracts",
            )
        take(entry)
        plan_id = value.get("plan_id")
        if not isinstance(plan_id, str):
            entry.lock.release()
            raise ContractError("Select a stored plan identifier")

        def execute() -> None:
            try:
                RepairTransaction(entry.target, journal).apply(incident_id, plan_id)
            finally:
                entry.lock.release()

        pool.submit(execute)
        return {"incident_id": incident_id, "state": "repair_queued"}

    @app.post("/api/incidents/{incident_id}/explain", status_code=202)
    def explanation(incident_id: str) -> dict[str, Any]:
        """Request an optional explanation while keeping model output outside control decisions."""
        if model is None:
            raise HTTPException(409, "No local model configured")
        entry = incident_target(incident_id)
        take(entry)

        def execute() -> None:
            try:
                record = journal.get(incident_id)
                result = explain(model, record)
                record["advisor"] = result
                journal.append(incident_id, "model_explanation", result)
                journal.save(record)
            finally:
                entry.lock.release()

        pool.submit(execute)
        return {"incident_id": incident_id, "state": "explanation_queued"}

    @app.get("/api/incidents/{incident_id}/report")
    def report(incident_id: str, format: str = "markdown") -> Response:
        """Download a self-contained report with actual observations and recovery outcome."""
        record = journal.get(incident_id)
        if format == "json":
            return Response(
                canonical(record),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{record["id"]}.json"'},
            )
        if format != "markdown":
            raise ContractError("Report format must be markdown or json")
        return Response(
            markdown_report(record),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{record["id"]}.md"'},
        )

    @app.post("/api/lab/scenario")
    def inject(value: dict[str, Any]) -> dict[str, Any]:
        """Change only owned demo configurations, with no concurrent investigation or repair."""
        if lab is None:
            raise HTTPException(404, "No lab is running")
        entry = next(item for item in registrations.values() if item.managed)
        take(entry)
        try:
            lab.scenario(value.get("scenario", ""))
        finally:
            entry.lock.release()
        return {"state": "injected", "target_id": entry.id}

    @app.post("/api/lab/restart")
    def restart() -> dict[str, Any]:
        """Demonstrate the effect of restarting owned processes with persisted settings intact."""
        if lab is None:
            raise HTTPException(404, "No lab is running")
        entry = next(item for item in registrations.values() if item.managed)
        take(entry)
        try:
            lab.restart()
        finally:
            entry.lock.release()
        return {"state": "restarted", "target_id": entry.id}

    @app.post("/api/traces")
    def trace_import(value: dict[str, Any]) -> dict[str, Any]:
        """Analyze an operator-imported OTLP export locally, without outbound model traffic."""
        return analyze_traces(value)

    @app.get("/api/lab/traces")
    def lab_traces() -> dict[str, Any]:
        """Analyze historical operations actually recorded by the owned application fixture."""
        if lab is None:
            raise HTTPException(404, "No lab is running")
        return analyze_traces(lab.export_traces())

    return app
