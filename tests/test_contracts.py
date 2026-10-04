"""Reject malformed or unsafe operator contracts before any adapter can access them."""

from pathlib import Path
from typing import Any

import pytest

from opsresolve.domain import (
    ContractError,
    Target,
    pointer_get,
    pointer_set,
    same_value,
    strict_json,
)


def manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "name": "Test app",
        "entry": "api",
        "services": [{"id": "api", "url": "http://127.0.0.1:12345/business"}],
    }


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:pass@localhost",
        "http://localhost/?token=a",
        "https://localhost/#fragment",
        "http://localhost:99999",
        "http://localhost/\nsecret",
    ],
)
def test_invalid_http_targets(tmp_path: Path, url: str) -> None:
    value = manifest()
    value["services"][0]["url"] = url
    with pytest.raises(ContractError):
        Target.from_dict(value, tmp_path)


@pytest.mark.parametrize("file", ["../outside.json", "/etc/shadow", ".", "nested/../../outside.json"])
def test_file_scope(tmp_path: Path, file: str) -> None:
    value = manifest()
    value["bindings"] = [{"id": "setting", "service": "api", "file": file, "pointer": "/a", "expected": 1}]
    with pytest.raises(ContractError):
        Target.from_dict(value, tmp_path)


def test_symlinks_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "other.json").write_text('{"a":1}')
    (tmp_path / "link.json").symlink_to(tmp_path / "other.json")
    value = manifest()
    value["bindings"] = [{"id": "setting", "service": "api", "file": "link.json", "pointer": "/a", "expected": 1}]
    with pytest.raises(ContractError, match="Symbolic"):
        Target.from_dict(value, tmp_path)


@pytest.mark.parametrize("data", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}', "not json"])
def test_strict_json(data: str) -> None:
    with pytest.raises(ContractError):
        strict_json(data)


def test_dependency_cycles_and_unreachable_services(tmp_path: Path) -> None:
    value = manifest()
    value["services"].append({"id": "db", "url": "http://localhost:54321/query"})
    with pytest.raises(ContractError, match="reachable"):
        Target.from_dict(value, tmp_path)
    value["dependencies"] = [{"source": "api", "target": "db"}, {"source": "db", "target": "api"}]
    with pytest.raises(ContractError, match="DAG"):
        Target.from_dict(value, tmp_path)


def test_json_pointer_escaped_array_fields() -> None:
    value = {"a/b": [{"~key": "before"}]}
    assert pointer_get(value, "/a~1b/0/~0key") == "before"
    pointer_set(value, "/a~1b/0/~0key", "after")
    assert value == {"a/b": [{"~key": "after"}]}
    for pointer in ("/a~2b", "/a~1b/01", "/absent", ""):
        with pytest.raises(ContractError):
            pointer_get(value, pointer)
    assert not same_value(True, 1)


def test_secret_contracts_are_automatically_sensitive(tmp_path: Path) -> None:
    value = manifest()
    value["bindings"] = [
        {
            "id": "setting",
            "service": "api",
            "file": "config.json",
            "pointer": "/api_token",
            "expected": "a",
            "repairable": True,
            "reload": "hot",
        }
    ]
    assert Target.from_dict(value, tmp_path).bindings[0].sensitive
