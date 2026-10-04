"""SQLite incident persistence and append-only event-chain integrity checks."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .domain import ContractError, canonical, digest, strict_json, timestamp


class Journal:
    """Use short independent transactions so workers and browser readers can coexist."""

    def __init__(self, path: Path):
        """Create a host-local journal without storing provider keys or model weights."""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS incidents(
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, target_name TEXT NOT NULL,
                    record TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    incident_id TEXT NOT NULL, sequence INTEGER NOT NULL, created_at TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL,
                    hash TEXT NOT NULL, PRIMARY KEY(incident_id,sequence),
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                );
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Commit or roll back a short transaction and always close its connection."""
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, record: dict[str, Any]) -> None:
        """Persist an incident before a worker emits its first event."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO incidents VALUES(?,?,?,?)",
                (record["id"], record["created_at"], record["target_name"], canonical(record)),
            )

    def save(self, record: dict[str, Any]) -> None:
        """Replace the current incident snapshot; historical events remain append-only."""
        with self._connect() as connection:
            cursor = connection.execute("UPDATE incidents SET record=? WHERE id=?", (canonical(record), record["id"]))
            if cursor.rowcount != 1:
                raise ContractError("Unknown incident")

    def get(self, incident_id: str) -> dict[str, Any]:
        """Read the latest workflow snapshot for one incident."""
        with self._connect() as connection:
            row = connection.execute("SELECT record FROM incidents WHERE id=?", (incident_id,)).fetchone()
        if row is None:
            raise ContractError("Unknown incident")
        result: dict[str, Any] = strict_json(row[0])
        return result

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent summaries without loading large captured response bodies."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record FROM incidents ORDER BY created_at DESC LIMIT ?",
                (min(max(limit, 1), 100),),
            ).fetchall()
        keys = ("id", "created_at", "target_name", "state", "spent", "budget", "target_id")
        return [{key: record.get(key) for key in keys} for record in (strict_json(row[0]) for row in rows)]

    def append(self, incident_id: str, kind: str, payload: dict[str, Any]) -> None:
        """Serialize each sequence allocation and hash its exact prior event and content."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            last = connection.execute(
                "SELECT sequence, hash FROM events WHERE incident_id=? ORDER BY sequence DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
            sequence, previous = (last[0] + 1, last[1]) if last else (1, "")
            created = timestamp()
            encoded = canonical(payload)
            event_hash = digest(canonical([incident_id, sequence, created, kind, encoded, previous]).encode())
            connection.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                (incident_id, sequence, created, kind, encoded, previous, event_hash),
            )

    def events(self, incident_id: str) -> list[dict[str, Any]]:
        """Export ordered events and their integrity links."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE incident_id=? ORDER BY sequence", (incident_id,)
            ).fetchall()
        return [{**dict(row), "payload": strict_json(row["payload"])} for row in rows]

    def verify(self, incident_id: str) -> bool:
        """Detect a broken event chain; database owners can still replace and rehash records."""
        previous = ""
        for expected_sequence, event in enumerate(self.events(incident_id), 1):
            if event["sequence"] != expected_sequence or event["previous_hash"] != previous:
                return False
            expected = digest(
                canonical(
                    [
                        incident_id,
                        event["sequence"],
                        event["created_at"],
                        event["kind"],
                        canonical(event["payload"]),
                        previous,
                    ]
                ).encode()
            )
            if event["hash"] != expected:
                return False
            previous = expected
        return True
