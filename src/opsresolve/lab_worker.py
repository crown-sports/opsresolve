"""A disposable HTTP application whose business requests traverse real processes and SQLite."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from .domain import canonical, strict_json


def serve(config_path: Path) -> None:
    """Read runtime configuration on every request to exercise real hot-reloaded repairs."""
    startup = strict_json(config_path.read_bytes())
    workspace = config_path.parent.parent

    def emit_span(
        trace_id: str,
        span_id: str,
        parent: str,
        name: str,
        start: int,
        failed: bool,
        attributes: dict[str, Any],
    ) -> None:
        """Append one actual operation as an OTLP JSON envelope in the owned fixture workspace."""
        values = [
            {
                "key": key,
                "value": {"intValue" if isinstance(value, int) else "stringValue": str(value)},
            }
            for key, value in attributes.items()
        ]
        span = {
            "traceId": trace_id,
            "spanId": span_id,
            "parentSpanId": parent,
            "name": name,
            "startTimeUnixNano": str(start),
            "endTimeUnixNano": str(time.time_ns()),
            "status": {"code": 2 if failed else 1},
            "attributes": values,
        }
        envelope = {
            "resourceSpans": [
                {
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": startup["service"]}}]},
                    "scopeSpans": [{"spans": [span]}],
                }
            ]
        }
        descriptor = os.open(workspace / "traces.ndjson", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, (canonical(envelope) + "\n").encode())
        finally:
            os.close(descriptor)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            """Keep lab processes quiet; diagnostic facts are captured over HTTP."""
            return

        def respond(self, status: int, value: dict[str, Any]) -> None:
            """Return a complete bounded JSON response even when a caller has timed out."""
            body = json.dumps(value, ensure_ascii=False).encode()
            self.response_status = status
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_GET(self) -> None:
            """Propagate trace context across the actual service dependency calls."""
            parent = self.headers.get("traceparent", "")
            match = re.fullmatch(r"00-([0-9a-f]{32})-([0-9a-f]{16})-01", parent)
            self.trace_id = match[1] if match and int(match[1], 16) else secrets.token_hex(16)
            parent_id = match[2] if match and int(match[2], 16) else ""
            self.span_id = secrets.token_hex(8)
            self.response_status = 500
            started = time.time_ns()
            try:
                self.business_request()
            finally:
                emit_span(
                    self.trace_id,
                    self.span_id,
                    parent_id,
                    "GET " + self.path,
                    started,
                    self.response_status >= 400,
                    {"http.response.status_code": self.response_status, "http.route": self.path},
                )

        def business_request(self) -> None:
            """Exercise required upstream calls and an actual read-only SQLite query."""
            if self.path == "/health":
                self.respond(200, {"alive": True})
                return
            config = strict_json(config_path.read_bytes())
            if self.path != config["path"]:
                self.respond(404, {"error": "route_not_found", "received_path": self.path})
                return
            if config.get("delay_seconds"):
                time.sleep(config["delay_seconds"])
            if config.get("application_failure"):
                self.respond(500, {"error": "application_invariant_failed", "service": config["service"]})
                return
            output: dict[str, Any] = {"service": config["service"], "ready": True}
            if config.get("database"):
                database = workspace / config["database"]
                database_start = time.time_ns()
                database_failed = False
                database_attributes = {
                    "db.system.name": "sqlite",
                    "db.namespace": config["database"],
                }
                try:
                    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
                        rows = connection.execute("SELECT name, quantity FROM inventory ORDER BY name").fetchall()
                    output["inventory"] = rows
                except sqlite3.Error as exc:
                    database_failed = True
                    database_attributes["error.type"] = type(exc).__name__
                    self.respond(
                        500,
                        {
                            "error": "database_query_failed",
                            "detail": str(exc),
                            "database": config["database"],
                            "service": config["service"],
                        },
                    )
                    return
                finally:
                    emit_span(
                        self.trace_id,
                        secrets.token_hex(8),
                        self.span_id,
                        "database.read",
                        database_start,
                        database_failed,
                        database_attributes,
                    )
            upstreams = {}
            opener = build_opener(ProxyHandler({}))
            for dependency, url in config.get("upstreams", {}).items():
                client_id = secrets.token_hex(8)
                client_start = time.time_ns()
                client_failed = False
                client_attributes: dict[str, Any] = {"server.address": url}
                try:
                    headers = {"traceparent": f"00-{self.trace_id}-{client_id}-01"}
                    with opener.open(Request(url, method="GET", headers=headers), timeout=1.2) as response:
                        client_attributes["http.response.status_code"] = response.code
                        upstreams[dependency] = strict_json(response.read(65536))
                except HTTPError as exc:
                    client_failed = True
                    client_attributes["http.response.status_code"] = exc.code
                    self.respond(
                        503,
                        {
                            "error": "upstream_failure",
                            "dependency": dependency,
                            "upstream_status": exc.code,
                            "upstream_url": url,
                        },
                    )
                    return
                except (URLError, TimeoutError) as exc:
                    client_failed = True
                    client_attributes["error.type"] = type(exc).__name__
                    self.respond(
                        503,
                        {
                            "error": "upstream_unreachable",
                            "dependency": dependency,
                            "detail": str(exc),
                            "upstream_url": url,
                        },
                    )
                    return
                finally:
                    emit_span(
                        self.trace_id,
                        client_id,
                        self.span_id,
                        "call " + dependency,
                        client_start,
                        client_failed,
                        client_attributes,
                    )
            output["dependencies"] = upstreams
            self.respond(200, output)

    server = ThreadingHTTPServer(("127.0.0.1", startup["port"]), Handler)
    server.daemon_threads = True
    server.serve_forever(poll_interval=0.1)


def main() -> None:
    """Run only a configuration explicitly supplied by the owned lab supervisor."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    serve(args.config.resolve())


if __name__ == "__main__":
    main()
