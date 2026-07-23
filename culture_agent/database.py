from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    creator TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL CHECK(kind IN ('book', 'film')),
    status TEXT NOT NULL DEFAULT 'finished',
    rating REAL CHECK(rating IS NULL OR (rating >= 0 AND rating <= 10)),
    reflection TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title, creator, reflection, tags,
    content='entries',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
  INSERT INTO entries_fts(rowid, title, creator, reflection, tags)
  VALUES (new.id, new.title, new.creator, new.reflection, new.tags_json);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
  INSERT INTO entries_fts(entries_fts, rowid, title, creator, reflection, tags)
  VALUES ('delete', old.id, old.title, old.creator, old.reflection, old.tags_json);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
  INSERT INTO entries_fts(entries_fts, rowid, title, creator, reflection, tags)
  VALUES ('delete', old.id, old.title, old.creator, old.reflection, old.tags_json);
  INSERT INTO entries_fts(rowid, title, creator, reflection, tags)
  VALUES (new.id, new.title, new.creator, new.reflection, new.tags_json);
END;
"""


class CultureDatabase:
    def __init__(self, path: str | Path = "data/culture_agent.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # Connections are intentionally short-lived so the local database can
        # be backed up or exported without coordinating a long-running pool.
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def add_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        # User-authored reflections are stored verbatim. Derived tags live in a
        # separate field and can be corrected without rewriting the source text.
        now = datetime.now(timezone.utc).isoformat()
        tags = sorted({str(tag).strip() for tag in entry.get("tags", []) if str(tag).strip()})
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO entries
                (title, creator, kind, status, rating, reflection, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["title"].strip(),
                    entry.get("creator", "").strip(),
                    entry["kind"],
                    entry.get("status", "finished"),
                    entry.get("rating"),
                    entry.get("reflection", "").strip(),
                    json.dumps(tags, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            entry_id = cursor.lastrowid
        return self.get_entry(int(entry_id))

    def get_entry(self, entry_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            raise KeyError(f"Entry {entry_id} does not exist")
        return self._serialize(row)

    def list_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM entries ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._serialize(row) for row in rows]

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        cleaned = " ".join(part for part in query.replace('"', " ").split() if part)
        if not cleaned:
            return self.list_entries(limit)
        with self.connect() as connection:
            try:
                rows = connection.execute(
                    """
                    SELECT entries.* FROM entries_fts
                    JOIN entries ON entries.id = entries_fts.rowid
                    WHERE entries_fts MATCH ?
                    ORDER BY bm25(entries_fts)
                    LIMIT ?
                    """,
                    (cleaned, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                pattern = f"%{cleaned}%"
                rows = connection.execute(
                    """
                    SELECT * FROM entries
                    WHERE title LIKE ? OR creator LIKE ? OR reflection LIKE ? OR tags_json LIKE ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (pattern, pattern, pattern, pattern, limit),
                ).fetchall()
        return [self._serialize(row) for row in rows]

    def delete_entry(self, entry_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["tags"] = json.loads(result.pop("tags_json"))
        return result
