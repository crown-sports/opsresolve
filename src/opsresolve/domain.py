"""Immutable target contracts and serializable observations used by every adapter."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4


class ContractError(ValueError):
    """A target, evidence record, or mutation violates a declared contract."""


def timestamp() -> str:
    """Return an explicit UTC timestamp suitable for incident export."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def identifier(prefix: str) -> str:
    """Create a collision-resistant identifier without depending on wall-clock precision."""
    return f"{prefix}_{uuid4().hex}"


def digest(data: bytes) -> str:
    """Hash captured bytes; this is an integrity check, not an authenticity signature."""
    return hashlib.sha256(data).hexdigest()


def strict_json(data: str | bytes) -> Any:
    """Reject duplicate keys and non-finite numbers before interpreting a configuration."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ContractError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value: str) -> Any:
        raise ContractError(f"Non-finite JSON number: {value}")

    def finite_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise ContractError("Non-finite JSON number")
        return result

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float)
    except (ValueError, UnicodeError) as exc:
        raise ContractError(f"Invalid JSON: {exc}") from exc


def canonical(value: Any) -> str:
    """Encode finite JSON deterministically for journals and evidence quotes."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def http_url(value: Any) -> str:
    """Accept explicit HTTP targets without embedded credentials, fragments, or queries."""
    if not isinstance(value, str) or len(value) > 2048:
        raise ContractError("An HTTP URL must be a string of at most 2048 characters")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ContractError("Invalid HTTP URL") from exc
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
        or parts.query
        or any(ord(char) < 33 for char in value)
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ContractError("Use an http(s) URL without credentials, query parameters, or fragments")
    return value


def pointer_parts(pointer: str) -> tuple[str, ...]:
    """Decode a non-root RFC 6901 pointer and reject malformed escapes."""
    if not pointer.startswith("/") or len(pointer) > 512:
        raise ContractError("A binding needs a non-root JSON pointer")
    parts = pointer[1:].split("/")
    if any(re.search(r"~(?![01])", part) for part in parts):
        raise ContractError("Malformed JSON pointer escape")
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in parts)


def pointer_get(document: Any, pointer: str) -> Any:
    """Read an existing object or array field; never invent a missing setting."""
    current = document
    try:
        for part in pointer_parts(pointer):
            if isinstance(current, list):
                if not part.isdecimal() or (part != "0" and part.startswith("0")):
                    raise KeyError(part)
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                raise KeyError(part)
        return current
    except (KeyError, IndexError, TypeError) as exc:
        raise ContractError(f"Missing configuration field: {pointer}") from exc


def pointer_set(document: Any, pointer: str, value: Any) -> None:
    """Replace an existing field after the caller has checked its exact precondition."""
    parts = pointer_parts(pointer)
    parent = document
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    last = parts[-1]
    pointer_get(document, pointer)
    if isinstance(parent, list):
        parent[int(last)] = value
    else:
        parent[last] = value


def same_value(left: Any, right: Any) -> bool:
    """Compare JSON values without treating true as the integer one."""
    return canonical(left) == canonical(right)


def safe_file(root: Path, relative: str) -> Path:
    """Constrain configuration access to regular files beneath a host-selected workspace."""
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {".", ".."} for part in path.parts):
        raise ContractError("Configuration files must use relative paths within the target workspace")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ContractError("Symbolic links are not configuration targets")
    if current.exists() and not current.is_file():
        raise ContractError("Configuration target is not a regular file")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ContractError("Configuration target escapes the workspace")
    return current


def _keys(value: Any, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise ContractError(f"Expected fields {sorted(required)}; allowed fields {sorted(allowed)}")
    return value


def _name(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", value):
        raise ContractError("Identifiers need 1–48 letters, digits, underscores, or hyphens")
    return value


def _text(value: Any, limit: int = 160) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ContractError(f"Text must contain 1–{limit} characters")
    return value


def _number(value: Any, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("Expected a finite numeric value")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ContractError(f"Numeric value must be between {minimum} and {maximum}")
    return number


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    url: str
    health_url: str | None = None
    expected_status: int = 200
    body_contains: str = ""
    timeout_seconds: float = 2.0
    cost: float = 1.0
    headers_env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Binding:
    id: str
    service: str
    file: str
    pointer: str
    expected: Any
    cost: float = 0.25
    repairable: bool = False
    sensitive: bool = False
    reload: str = "manual"


@dataclass(frozen=True)
class Target:
    name: str
    entry: str
    services: tuple[Service, ...]
    dependencies: tuple[tuple[str, str], ...]
    bindings: tuple[Binding, ...]
    root: Path = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, root: Path) -> Target:
        """Validate a bounded dependency DAG and host-scoped configuration contracts."""
        obj = _keys(
            value,
            {"version", "name", "entry", "services", "dependencies", "bindings"},
            {"version", "name", "entry", "services"},
        )
        if obj["version"] != 1 or isinstance(obj["version"], bool):
            raise ContractError("Only target manifest version 1 is supported")
        raw_services = obj["services"]
        if not isinstance(raw_services, list) or not 1 <= len(raw_services) <= 16:
            raise ContractError("A target needs 1–16 services")
        services = []
        for item in raw_services:
            item = _keys(
                item,
                {
                    "id",
                    "name",
                    "url",
                    "health_url",
                    "expected_status",
                    "body_contains",
                    "timeout_seconds",
                    "cost",
                    "headers_env",
                },
                {"id", "url"},
            )
            status = _number(item.get("expected_status", 200), 100, 599)
            if not status.is_integer():
                raise ContractError("Expected status must be an HTTP status integer")
            needle = item.get("body_contains", "")
            if not isinstance(needle, str) or len(needle) > 512:
                raise ContractError("body_contains must be a string of at most 512 characters")
            headers = item.get("headers_env", {})
            if not isinstance(headers, dict) or len(headers) > 8:
                raise ContractError("headers_env must map at most eight headers to environment names")
            for header, variable in headers.items():
                if (
                    not re.fullmatch(r"[A-Za-z0-9-]{1,64}", header)
                    or not isinstance(variable, str)
                    or not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,100}", variable)
                ):
                    raise ContractError("Invalid HTTP header or environment variable name")
            services.append(
                Service(
                    _name(item["id"]),
                    _text(item.get("name", item["id"])),
                    http_url(item["url"]),
                    http_url(item["health_url"]) if item.get("health_url") else None,
                    int(status),
                    needle,
                    _number(item.get("timeout_seconds", 2), 0.05, 10),
                    _number(item.get("cost", 1), 0.01, 100),
                    dict(headers),
                )
            )
        names = {service.id for service in services}
        if len(names) != len(services) or obj["entry"] not in names:
            raise ContractError("Service identifiers must be unique and entry must name a service")
        dependencies: list[tuple[str, str]] = []
        raw_edges = obj.get("dependencies", [])
        if not isinstance(raw_edges, list) or len(raw_edges) > 64:
            raise ContractError("dependencies must contain at most 64 edges")
        for edge in raw_edges:
            edge = _keys(edge, {"source", "target"}, {"source", "target"})
            source, target = edge["source"], edge["target"]
            if source not in names or target not in names or source == target:
                raise ContractError("Dependency endpoints must name distinct declared services")
            dependencies.append((source, target))
        if len(set(dependencies)) != len(dependencies):
            raise ContractError("Duplicate dependency edge")
        adjacency = {name: [b for a, b in dependencies if a == name] for name in names}
        visited: set[str] = set()
        active: set[str] = set()

        def visit(node: str) -> None:
            if node in active:
                raise ContractError("Dependencies must form a DAG in manifest version 1")
            if node in visited:
                return
            active.add(node)
            for child in adjacency[node]:
                visit(child)
            active.remove(node)
            visited.add(node)

        visit(obj["entry"])
        if visited != names:
            raise ContractError("Every service must be reachable from the entry service")
        raw_bindings = obj.get("bindings", [])
        if not isinstance(raw_bindings, list) or len(raw_bindings) > 32:
            raise ContractError("bindings must contain at most 32 contracts")
        bindings = []
        for item in raw_bindings:
            item = _keys(
                item,
                {
                    "id",
                    "service",
                    "file",
                    "pointer",
                    "expected",
                    "cost",
                    "repairable",
                    "sensitive",
                    "reload",
                },
                {"id", "service", "file", "pointer", "expected"},
            )
            if item["service"] not in names:
                raise ContractError("A binding must belong to a declared service")
            relative = _text(item["file"], 512)
            safe_file(root.resolve(), relative)
            pointer = _text(item["pointer"], 512)
            pointer_parts(pointer)
            expected = item["expected"]
            if isinstance(expected, dict):
                expected = _keys(expected, {"url_of"}, {"url_of"})
                if expected["url_of"] not in names:
                    raise ContractError("url_of must name a declared service")
            elif not isinstance(expected, (str, int, float, bool, type(None))):
                raise ContractError("Expected configuration values must be scalar or use url_of")
            canonical(expected)
            for flag in ("repairable", "sensitive"):
                if flag in item and not isinstance(item[flag], bool):
                    raise ContractError(f"{flag} must be a boolean")
            sensitive = item.get("sensitive", False) or bool(
                re.search(r"password|secret|token|api.?key|credential", pointer, re.I)
            )
            reload = item.get("reload", "manual")
            if reload not in {"hot", "manual"}:
                raise ContractError("reload must be hot or manual")
            bindings.append(
                Binding(
                    _name(item["id"]),
                    item["service"],
                    relative,
                    pointer,
                    expected,
                    _number(item.get("cost", 0.25), 0.01, 100),
                    item.get("repairable", False),
                    sensitive,
                    reload,
                )
            )
        if len({binding.id for binding in bindings}) != len(bindings):
            raise ContractError("Binding identifiers must be unique")
        paths = [(binding.file, binding.pointer) for binding in bindings]
        if len(set(paths)) != len(paths):
            raise ContractError("A configuration field can have only one binding")
        return cls(
            _text(obj["name"]),
            obj["entry"],
            tuple(services),
            tuple(dependencies),
            tuple(bindings),
            root.resolve(),
        )

    @classmethod
    def load(cls, path: Path) -> Target:
        """Read a bounded manifest; its parent directory is the configuration workspace."""
        data = path.read_bytes()
        if len(data) > 131072:
            raise ContractError("Target manifests must be at most 128 KiB")
        return cls.from_dict(strict_json(data), path.resolve().parent)

    def expected_value(self, binding: Binding) -> Any:
        """Resolve a configuration contract from declared intent, never from a fault label."""
        if isinstance(binding.expected, dict):
            return next(service.url for service in self.services if service.id == binding.expected["url_of"])
        return binding.expected

    def to_dict(self) -> dict[str, Any]:
        """Export a portable manifest without a host filesystem root."""
        return {
            "version": 1,
            "name": self.name,
            "entry": self.entry,
            "services": [asdict(service) for service in self.services],
            "dependencies": [{"source": a, "target": b} for a, b in self.dependencies],
            "bindings": [asdict(binding) for binding in self.bindings],
        }


@dataclass(frozen=True)
class Probe:
    id: str
    kind: str
    subject: str
    cost: float


@dataclass(frozen=True)
class Fault:
    id: str
    kind: str
    service: str
    binding: str | None
    title: str


@dataclass(frozen=True)
class Observation:
    id: str
    probe_id: str
    kind: str
    subject: str
    outcome: str
    started_at: str
    duration_ms: float
    facts: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize captured facts for the journal and incident report."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Observation:
        """Rehydrate a host-owned observation without rerunning a diagnostic probe."""
        return cls(**value)
