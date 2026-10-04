"""Typed read-only HTTP and JSON adapters with bounded capture and explicit unknowns."""

from __future__ import annotations

import os
import re
import socket
import ssl
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .domain import (
    ContractError,
    Observation,
    Probe,
    Target,
    canonical,
    digest,
    identifier,
    pointer_get,
    safe_file,
    same_value,
    strict_json,
    timestamp,
)


def redact(text: str) -> str:
    """Remove common credential assignments before text enters a report or model prompt."""
    text = re.sub(
        r'(?i)(["\']?(?:password|secret|token|api[_-]?key|authorization)["\']?\s*[:=]\s*)'
        r'("[^"\n]*"|\'[^\'\n]*\'|[^\s,;\}\]]+)',
        r'\1"[redacted]"',
        text,
    )
    return re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", text)


class NoRedirect(HTTPRedirectHandler):
    """Keep requests on operator-declared endpoints, including HTTP error responses."""

    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        """Return the redirect as an observation rather than following a new endpoint."""
        return None


class ProbeExecutor:
    """Dispatch only declared probe types; no model-generated command is executable."""

    def __init__(self, target: Target):
        self.target = target
        self.strategies: dict[str, Callable[[Probe], tuple[str, dict[str, Any]]]] = {
            "http": self._http,
            "live": self._http,
            "config": self._config,
        }

    def run(self, probe: Probe) -> Observation:
        """Capture one attempt and its duration; unavailable evidence is never a passing check."""
        started = timestamp()
        before = time.perf_counter()
        try:
            outcome, facts = self.strategies[probe.kind](probe)
        except (OSError, ContractError, ValueError, KeyError) as exc:
            outcome, facts = "unknown", {"error": redact(str(exc))[:500]}
        return Observation(
            identifier("ev"),
            probe.id,
            probe.kind,
            probe.subject,
            outcome,
            started,
            round((time.perf_counter() - before) * 1000, 3),
            facts,
        )

    def _http(self, probe: Probe) -> tuple[str, dict[str, Any]]:
        service = next(item for item in self.target.services if item.id == probe.subject)
        url = service.health_url if probe.kind == "live" else service.url
        if url is None:
            raise ContractError("No liveness endpoint declared")
        headers = {"User-Agent": "OpsResolve/0.1", "Accept": "application/json,text/plain,*/*"}
        for header, variable in service.headers_env.items():
            if variable not in os.environ:
                return "unknown", {
                    "url": url,
                    "error": f"Required environment variable {variable} is missing",
                }
            headers[header] = os.environ[variable]
        opener = build_opener(ProxyHandler({}), NoRedirect())
        request = Request(url, headers=headers, method="GET")
        facts: dict[str, Any] = {
            "url": url,
            "expected_status": 200 if probe.kind == "live" else service.expected_status,
        }
        try:
            try:
                response = opener.open(request, timeout=service.timeout_seconds)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.code
                captured = response.read(65537)
                truncated = len(captured) > 65536
                body = captured[:65536]
                text = redact(body.decode("utf-8", errors="replace"))
                facts.update(
                    status=status,
                    body=text[:4096],
                    body_sha256=digest(body),
                    captured_bytes=len(body),
                    body_truncated=truncated or len(text) > 4096,
                    content_type=response.headers.get("Content-Type", ""),
                )
                needle = service.body_contains if probe.kind == "http" else ""
                facts["body_contract_met"] = not needle or needle in body.decode("utf-8", errors="replace")
                healthy = status == facts["expected_status"] and facts["body_contract_met"]
                return ("ok" if healthy else "failure"), facts
        except TimeoutError:
            return "unknown", {
                **facts,
                "error": "HTTP check exceeded its timeout",
                "phase": "timeout",
            }
        except URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return "unknown", {
                    **facts,
                    "error": "HTTP check exceeded its timeout",
                    "phase": "timeout",
                }
            if isinstance(reason, socket.gaierror):
                phase = "dns"
            elif isinstance(reason, ssl.SSLError):
                phase = "tls"
            elif isinstance(reason, ConnectionRefusedError):
                phase = "connection_refused"
            else:
                phase = "transport"
            return "unreachable", {**facts, "error": redact(str(reason))[:500], "phase": phase}

    def _config(self, probe: Probe) -> tuple[str, dict[str, Any]]:
        binding = next(item for item in self.target.bindings if item.id == probe.subject)
        path = safe_file(self.target.root, binding.file)
        if path.stat().st_size > 1048576:
            raise ContractError("Configuration files must be at most 1 MiB")
        with path.open("rb") as stream:
            data = stream.read(1048577)
        if len(data) > 1048576:
            raise ContractError("Configuration files must be at most 1 MiB")
        current = pointer_get(strict_json(data), binding.pointer)
        expected = self.target.expected_value(binding)
        outcome = "ok" if same_value(current, expected) else "drift"
        facts = {
            "file": binding.file,
            "pointer": binding.pointer,
            "file_sha256": digest(data),
            "current": "[redacted]" if binding.sensitive else current,
            "expected": "[redacted]" if binding.sensitive else expected,
            "sensitive": binding.sensitive,
            "repairable": binding.repairable,
            "reload": binding.reload,
        }
        facts["quote"] = canonical(
            {"pointer": binding.pointer, "current": facts["current"], "expected": facts["expected"]}
        )
        return outcome, facts
