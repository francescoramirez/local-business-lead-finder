"""Activity history."""

from __future__ import annotations

import sqlite3

from leadfinder.models import Activity
from leadfinder.storage.mapping import row_to_activity
from leadfinder.workflow import to_iso, utc_now


class ActivitiesMixin:
    _conn: sqlite3.Connection

    def add_activity(
        self,
        place_id: str,
        activity_type: str,
        *,
        note: str = "",
        contact_method: str = "",
        outcome: str = "",
        created_at: str | None = None,
        metadata_json: str = "",
        reverses_activity_id: int = 0,
        commit: bool = True,
    ) -> Activity:
        self.mark_seen(place_id, seen_at=created_at, commit=False)  # type: ignore[attr-defined]
        activity_id = self._add_activity(
            place_id,
            activity_type,
            created_at=created_at,
            note=note,
            contact_method=contact_method,
            outcome=outcome,
            metadata_json=metadata_json,
            reverses_activity_id=reverses_activity_id,
        )
        if commit:
            self._conn.commit()
        rows = self.list_activities(place_id)
        for item in rows:
            if item.id == activity_id:
                return item
        return rows[0]

    def _add_activity(
        self,
        place_id: str,
        activity_type: str,
        *,
        created_at: str | None = None,
        note: str = "",
        contact_method: str = "",
        outcome: str = "",
        metadata_json: str = "",
        reverses_activity_id: int = 0,
    ) -> int:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO activities (
                place_id, activity_type, created_at, note, contact_method, outcome,
                metadata_json, reverses_activity_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                place_id,
                activity_type,
                stamp,
                note,
                contact_method,
                outcome,
                metadata_json,
                reverses_activity_id or None,
            ),
        )
        self._conn.execute(
            "UPDATE leads_local SET last_activity_at = ? WHERE place_id = ?",
            (stamp, place_id),
        )
        return int(cursor.lastrowid or 0)

    def list_activities(self, place_id: str) -> list[Activity]:
        cursor = self._conn.execute(
            """
            SELECT * FROM activities
            WHERE place_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (place_id,),
        )
        return [row_to_activity(row) for row in cursor.fetchall()]

    def list_all_activities(self) -> list[Activity]:
        cursor = self._conn.execute(
            "SELECT * FROM activities ORDER BY created_at ASC, id ASC"
        )
        return [row_to_activity(row) for row in cursor.fetchall()]
