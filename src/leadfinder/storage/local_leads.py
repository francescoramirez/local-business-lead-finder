from __future__ import annotations

import sqlite3
from pathlib import Path

from leadfinder.models import CONTACT_STATUSES, LocalLeadState, utc_now_iso
from leadfinder.paths import default_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads_local (
    place_id TEXT PRIMARY KEY,
    contact_status TEXT NOT NULL DEFAULT 'new',
    notes TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_contacted_at TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT ''
);
"""


def _row_to_state(row: sqlite3.Row) -> LocalLeadState:
    return LocalLeadState(
        place_id=row["place_id"],
        contact_status=row["contact_status"],
        notes=row["notes"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        last_contacted_at=row["last_contacted_at"],
        tags=row["tags"],
    )


class LocalLeadStore:
    """SQLite store for user-generated lead metadata only (not Places content)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get(self, place_id: str) -> LocalLeadState | None:
        cursor = self._conn.execute(
            "SELECT * FROM leads_local WHERE place_id = ?",
            (place_id,),
        )
        row = cursor.fetchone()
        return _row_to_state(row) if row else None

    def get_many(self, place_ids: list[str]) -> dict[str, LocalLeadState]:
        if not place_ids:
            return {}
        placeholders = ",".join("?" * len(place_ids))
        cursor = self._conn.execute(
            f"SELECT * FROM leads_local WHERE place_id IN ({placeholders})",
            place_ids,
        )
        return {row["place_id"]: _row_to_state(row) for row in cursor.fetchall()}

    def mark_seen(self, place_id: str, *, seen_at: str | None = None) -> LocalLeadState:
        now = seen_at or utc_now_iso()
        existing = self.get(place_id)
        if existing is None:
            state = LocalLeadState(
                place_id=place_id,
                first_seen_at=now,
                last_seen_at=now,
            )
            self._conn.execute(
                """
                INSERT INTO leads_local (
                    place_id, contact_status, notes, first_seen_at, last_seen_at,
                    last_contacted_at, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.place_id,
                    state.contact_status,
                    state.notes,
                    state.first_seen_at,
                    state.last_seen_at,
                    state.last_contacted_at,
                    state.tags,
                ),
            )
            self._conn.commit()
            return state
        self._conn.execute(
            "UPDATE leads_local SET last_seen_at = ? WHERE place_id = ?",
            (now, place_id),
        )
        self._conn.commit()
        existing.last_seen_at = now
        return existing

    def set_contact_status(self, place_id: str, status: str) -> LocalLeadState:
        if status not in CONTACT_STATUSES:
            raise ValueError(f"Unknown contact status: {status}")
        now = utc_now_iso()
        state = self.mark_seen(place_id, seen_at=now)
        contacted_at = state.last_contacted_at
        if status != "new" and not contacted_at:
            contacted_at = now
        self._conn.execute(
            """
            UPDATE leads_local
            SET contact_status = ?, last_contacted_at = ?
            WHERE place_id = ?
            """,
            (status, contacted_at, place_id),
        )
        self._conn.commit()
        state.contact_status = status
        state.last_contacted_at = contacted_at
        return state

    def set_notes(self, place_id: str, notes: str) -> LocalLeadState:
        state = self.mark_seen(place_id)
        self._conn.execute(
            "UPDATE leads_local SET notes = ? WHERE place_id = ?",
            (notes, place_id),
        )
        self._conn.commit()
        state.notes = notes
        return state
