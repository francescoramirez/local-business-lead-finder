from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from leadfinder.errors import BackupError
from leadfinder.models import Activity, LocalLeadState, SearchRun
from leadfinder.paths import default_db_path
from leadfinder.storage.schema import migrate, schema_version
from leadfinder.workflow import (
    CONTACT_STATUSES,
    ActivityType,
    parse_tags,
    to_iso,
    utc_now,
)


def _row_to_state(row: sqlite3.Row) -> LocalLeadState:
    keys = set(row.keys())
    return LocalLeadState(
        place_id=row["place_id"],
        contact_status=row["contact_status"],
        notes=row["notes"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        last_contacted_at=row["last_contacted_at"],
        tags=row["tags"],
        next_follow_up_at=row["next_follow_up_at"] if "next_follow_up_at" in keys else "",
        last_activity_at=row["last_activity_at"] if "last_activity_at" in keys else "",
        label=row["label"] if "label" in keys else "",
        opportunity_level=row["opportunity_level"] if "opportunity_level" in keys else "",
        opportunity_score=int(row["opportunity_score"] if "opportunity_score" in keys else 0),
        has_phone=bool(row["has_phone"] if "has_phone" in keys else 0),
    )


def _row_to_activity(row: sqlite3.Row) -> Activity:
    return Activity(
        id=int(row["id"]),
        place_id=row["place_id"],
        activity_type=row["activity_type"],
        created_at=row["created_at"],
        note=row["note"],
        contact_method=row["contact_method"],
        outcome=row["outcome"],
    )


class LocalLeadStore:
    """SQLite store for user-generated lead metadata only (not Places content)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        migrate(self._conn)

    @property
    def schema_version(self) -> int:
        return schema_version(self._conn)

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            self._conn.execute("BEGIN")
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

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

    def list_all(self) -> list[LocalLeadState]:
        cursor = self._conn.execute(
            "SELECT * FROM leads_local ORDER BY last_seen_at DESC"
        )
        return [_row_to_state(row) for row in cursor.fetchall()]

    def mark_seen(
        self,
        place_id: str,
        *,
        seen_at: str | None = None,
        label: str = "",
        opportunity_level: str = "",
        opportunity_score: int | None = None,
        has_phone: bool | None = None,
        commit: bool = True,
    ) -> LocalLeadState:
        now = seen_at or to_iso(utc_now())
        existing = self.get(place_id)
        if existing is None:
            state = LocalLeadState(
                place_id=place_id,
                first_seen_at=now,
                last_seen_at=now,
                label=label,
                opportunity_level=opportunity_level,
                opportunity_score=opportunity_score or 0,
                has_phone=bool(has_phone),
            )
            self._conn.execute(
                """
                INSERT INTO leads_local (
                    place_id, contact_status, notes, first_seen_at, last_seen_at,
                    last_contacted_at, tags, next_follow_up_at, last_activity_at,
                    label, opportunity_level, opportunity_score, has_phone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.place_id,
                    state.contact_status,
                    state.notes,
                    state.first_seen_at,
                    state.last_seen_at,
                    state.last_contacted_at,
                    state.tags,
                    state.next_follow_up_at,
                    state.last_activity_at,
                    state.label,
                    state.opportunity_level,
                    state.opportunity_score,
                    int(state.has_phone),
                ),
            )
            self._add_activity(
                place_id,
                ActivityType.DISCOVERED.value,
                created_at=now,
                note="Lead discovered",
            )
            if commit:
                self._conn.commit()
            found = self.get(place_id)
            return found if found is not None else state
        new_label = label or existing.label
        new_level = opportunity_level or existing.opportunity_level
        new_score = existing.opportunity_score if opportunity_score is None else opportunity_score
        new_phone = existing.has_phone if has_phone is None else has_phone
        self._conn.execute(
            """
            UPDATE leads_local
            SET last_seen_at = ?, label = ?, opportunity_level = ?,
                opportunity_score = ?, has_phone = ?
            WHERE place_id = ?
            """,
            (now, new_label, new_level, new_score, int(new_phone), place_id),
        )
        if commit:
            self._conn.commit()
        existing.last_seen_at = now
        existing.label = new_label
        existing.opportunity_level = new_level
        existing.opportunity_score = new_score
        existing.has_phone = new_phone
        return existing

    def set_contact_status(
        self,
        place_id: str,
        status: str,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> LocalLeadState:
        if status not in CONTACT_STATUSES:
            raise ValueError(f"Unknown contact status: {status}")
        stamp = to_iso(utc_now(now))
        previous = self.get(place_id)
        state = self.mark_seen(place_id, seen_at=stamp, commit=False)
        if previous is not None and previous.contact_status == status:
            if commit:
                self._conn.commit()
            return state
        contacted_at = state.last_contacted_at
        if status != "new" and not contacted_at:
            contacted_at = stamp
        self._conn.execute(
            """
            UPDATE leads_local
            SET contact_status = ?, last_contacted_at = ?
            WHERE place_id = ?
            """,
            (status, contacted_at, place_id),
        )
        old = previous.contact_status if previous else "new"
        self._add_activity(
            place_id,
            ActivityType.STATUS_CHANGE.value,
            created_at=stamp,
            note=f"Status changed → {old.replace('_', ' ')} to {status.replace('_', ' ')}",
        )
        if commit:
            self._conn.commit()
        refreshed = self.get(place_id)
        if refreshed is None:
            state.contact_status = status
            state.last_contacted_at = contacted_at
            return state
        return refreshed

    def set_notes(self, place_id: str, notes: str, *, commit: bool = True) -> LocalLeadState:
        self.mark_seen(place_id, commit=False)
        self._conn.execute(
            "UPDATE leads_local SET notes = ? WHERE place_id = ?",
            (notes, place_id),
        )
        if commit:
            self._conn.commit()
        state = self.get(place_id)
        assert state is not None
        return state

    def set_tags(self, place_id: str, tags: str, *, commit: bool = True) -> LocalLeadState:
        cleaned = ", ".join(parse_tags(tags))
        self.mark_seen(place_id, commit=False)
        self._conn.execute(
            "UPDATE leads_local SET tags = ? WHERE place_id = ?",
            (cleaned, place_id),
        )
        if commit:
            self._conn.commit()
        state = self.get(place_id)
        assert state is not None
        return state

    def set_follow_up(
        self,
        place_id: str,
        when: str,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> LocalLeadState:
        stamp = to_iso(utc_now(now))
        self.mark_seen(place_id, seen_at=stamp, commit=False)
        self._conn.execute(
            "UPDATE leads_local SET next_follow_up_at = ? WHERE place_id = ?",
            (when, place_id),
        )
        note = "Follow-up cleared" if not when else f"Follow-up scheduled for {when}"
        self._add_activity(
            place_id,
            ActivityType.FOLLOW_UP.value,
            created_at=stamp,
            note=note,
        )
        if commit:
            self._conn.commit()
        state = self.get(place_id)
        assert state is not None
        return state

    def add_activity(
        self,
        place_id: str,
        activity_type: str,
        *,
        note: str = "",
        contact_method: str = "",
        outcome: str = "",
        created_at: str | None = None,
        commit: bool = True,
    ) -> Activity:
        self.mark_seen(place_id, seen_at=created_at, commit=False)
        activity_id = self._add_activity(
            place_id,
            activity_type,
            created_at=created_at,
            note=note,
            contact_method=contact_method,
            outcome=outcome,
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
    ) -> int:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO activities (
                place_id, activity_type, created_at, note, contact_method, outcome
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (place_id, activity_type, stamp, note, contact_method, outcome),
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
        return [_row_to_activity(row) for row in cursor.fetchall()]

    def record_search(
        self,
        *,
        business_preset: str,
        location: str,
        region: str,
        country: str,
        lead_count: int,
        high_opportunity_count: int,
        created_at: str | None = None,
    ) -> SearchRun:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO search_runs (
                created_at, business_preset, location, region, country,
                lead_count, high_opportunity_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stamp,
                business_preset,
                location,
                region,
                country,
                lead_count,
                high_opportunity_count,
            ),
        )
        self._conn.commit()
        return SearchRun(
            id=int(cursor.lastrowid or 0),
            created_at=stamp,
            business_preset=business_preset,
            location=location,
            region=region,
            country=country,
            lead_count=lead_count,
            high_opportunity_count=high_opportunity_count,
        )

    def list_searches(self, *, limit: int = 20) -> list[SearchRun]:
        cursor = self._conn.execute(
            "SELECT * FROM search_runs ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
        return [
            SearchRun(
                id=int(row["id"]),
                created_at=row["created_at"],
                business_preset=row["business_preset"],
                location=row["location"],
                region=row["region"],
                country=row["country"],
                lead_count=int(row["lead_count"]),
                high_opportunity_count=int(row["high_opportunity_count"]),
            )
            for row in cursor.fetchall()
        ]

    def delete_prospect(self, place_id: str) -> None:
        with self.transaction():
            self._conn.execute("DELETE FROM activities WHERE place_id = ?", (place_id,))
            self._conn.execute("DELETE FROM leads_local WHERE place_id = ?", (place_id,))

    def backup(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            target = sqlite3.connect(destination)
            try:
                self._conn.backup(target)
            finally:
                target.close()
        except sqlite3.Error as error:
            raise BackupError(f"Could not backup the local database: {error}") from error
        return destination

    def pipeline_rows(self) -> list[tuple[str, str, str]]:
        return [
            (item.contact_status, item.next_follow_up_at, item.opportunity_level)
            for item in self.list_all()
        ]
