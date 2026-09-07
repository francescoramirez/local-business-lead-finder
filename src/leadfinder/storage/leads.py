"""Lead rows and workflow updates."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from leadfinder.labels import MANUAL_PRIORITIES
from leadfinder.models import LocalLeadState
from leadfinder.storage.mapping import row_to_state
from leadfinder.workflow import (
    CONTACT_STATUSES,
    ActivityType,
    parse_tags,
    to_iso,
    utc_now,
)

LEAD_COLUMNS = """
    place_id, contact_status, notes, first_seen_at, last_seen_at,
    last_contacted_at, tags, next_follow_up_at, last_activity_at,
    label, opportunity_level, opportunity_score, has_phone,
    business_preset, source_location, region, country, website_status,
    campaign_id, manual_priority
"""


class LeadsMixin:
    _conn: sqlite3.Connection

    def get(self, place_id: str) -> LocalLeadState | None:
        cursor = self._conn.execute(
            "SELECT * FROM leads_local WHERE place_id = ?",
            (place_id,),
        )
        row = cursor.fetchone()
        return row_to_state(row) if row else None

    def get_many(self, place_ids: list[str]) -> dict[str, LocalLeadState]:
        if not place_ids:
            return {}
        placeholders = ",".join("?" * len(place_ids))
        cursor = self._conn.execute(
            f"SELECT * FROM leads_local WHERE place_id IN ({placeholders})",
            place_ids,
        )
        return {row["place_id"]: row_to_state(row) for row in cursor.fetchall()}

    def list_all(self) -> list[LocalLeadState]:
        cursor = self._conn.execute(
            "SELECT * FROM leads_local ORDER BY last_seen_at DESC"
        )
        return [row_to_state(row) for row in cursor.fetchall()]

    def mark_seen(
        self,
        place_id: str,
        *,
        seen_at: str | None = None,
        label: str = "",
        opportunity_level: str = "",
        opportunity_score: int | None = None,
        has_phone: bool | None = None,
        business_preset: str = "",
        source_location: str = "",
        region: str = "",
        country: str = "",
        website_status: str = "",
        campaign_id: int = 0,
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
                business_preset=business_preset,
                source_location=source_location,
                region=region,
                country=country,
                website_status=website_status,
                campaign_id=campaign_id,
            )
            self._conn.execute(
                f"""
                INSERT INTO leads_local ({LEAD_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    state.business_preset,
                    state.source_location,
                    state.region,
                    state.country,
                    state.website_status,
                    state.campaign_id or None,
                    state.manual_priority,
                ),
            )
            self._add_activity(  # type: ignore[attr-defined]
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
        new_preset = business_preset or existing.business_preset
        new_location = source_location or existing.source_location
        new_region = region or existing.region
        new_country = country or existing.country
        new_presence = website_status or existing.website_status
        new_campaign = campaign_id or existing.campaign_id
        self._conn.execute(
            """
            UPDATE leads_local
            SET last_seen_at = ?, label = ?, opportunity_level = ?,
                opportunity_score = ?, has_phone = ?, business_preset = ?,
                source_location = ?, region = ?, country = ?, website_status = ?,
                campaign_id = ?
            WHERE place_id = ?
            """,
            (
                now,
                new_label,
                new_level,
                new_score,
                int(new_phone),
                new_preset,
                new_location,
                new_region,
                new_country,
                new_presence,
                new_campaign or None,
                place_id,
            ),
        )
        if commit:
            self._conn.commit()
        existing.last_seen_at = now
        existing.label = new_label
        existing.opportunity_level = new_level
        existing.opportunity_score = new_score
        existing.has_phone = new_phone
        existing.business_preset = new_preset
        existing.source_location = new_location
        existing.region = new_region
        existing.country = new_country
        existing.website_status = new_presence
        existing.campaign_id = new_campaign
        return existing

    def set_contact_status(
        self,
        place_id: str,
        status: str,
        *,
        now: datetime | None = None,
        commit: bool = True,
        undo_of: int = 0,
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
        self._add_activity(  # type: ignore[attr-defined]
            place_id,
            ActivityType.STATUS_CHANGE.value,
            created_at=stamp,
            note=f"Status changed → {old.replace('_', ' ')} to {status.replace('_', ' ')}",
            outcome=status,
            metadata_json=json.dumps(
                {
                    "field": "contact_status",
                    "previous_value": old,
                    "new_value": status,
                    "reason": "undo" if undo_of else "",
                    "undo_of": str(undo_of) if undo_of else "",
                }
            ),
            reverses_activity_id=undo_of,
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

    def set_manual_priority(
        self,
        place_id: str,
        priority: str,
        *,
        commit: bool = True,
        undo_of: int = 0,
    ) -> LocalLeadState:
        if priority not in MANUAL_PRIORITIES:
            raise ValueError(f"Unknown manual priority: {priority}")
        existing = self.mark_seen(place_id, commit=False)
        previous = existing.manual_priority
        self._conn.execute(
            "UPDATE leads_local SET manual_priority = ? WHERE place_id = ?",
            (priority, place_id),
        )
        if previous != priority:
            self._add_activity(  # type: ignore[attr-defined]
                place_id,
                ActivityType.PRIORITY_CHANGE.value,
                note=f"Priority {previous} -> {priority}",
                metadata_json=json.dumps(
                    {
                        "field": "manual_priority",
                        "previous_value": previous,
                        "new_value": priority,
                        "reason": "undo" if undo_of else "",
                        "undo_of": str(undo_of) if undo_of else "",
                    }
                ),
                reverses_activity_id=undo_of,
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
        undo_of: int = 0,
    ) -> LocalLeadState:
        stamp = to_iso(utc_now(now))
        existing = self.mark_seen(place_id, seen_at=stamp, commit=False)
        previous = existing.next_follow_up_at
        self._conn.execute(
            "UPDATE leads_local SET next_follow_up_at = ? WHERE place_id = ?",
            (when, place_id),
        )
        note = "Follow-up cleared" if not when else f"Follow-up scheduled for {when}"
        self._add_activity(  # type: ignore[attr-defined]
            place_id,
            ActivityType.FOLLOW_UP.value,
            created_at=stamp,
            note=note,
            metadata_json=json.dumps(
                {
                    "field": "next_follow_up_at",
                    "previous_value": previous,
                    "new_value": when,
                    "reason": "undo" if undo_of else "",
                    "undo_of": str(undo_of) if undo_of else "",
                }
            ),
            reverses_activity_id=undo_of,
        )
        if commit:
            self._conn.commit()
        state = self.get(place_id)
        assert state is not None
        return state

    def delete_prospect(self, place_id: str) -> None:
        with self.transaction():  # type: ignore[attr-defined]
            self._conn.execute("DELETE FROM campaign_leads WHERE place_id = ?", (place_id,))
            self._conn.execute("DELETE FROM activities WHERE place_id = ?", (place_id,))
            self._conn.execute("DELETE FROM leads_local WHERE place_id = ?", (place_id,))

    def pipeline_rows(self) -> list[tuple[str, str, str]]:
        return [
            (item.contact_status, item.next_follow_up_at, item.opportunity_level)
            for item in self.list_all()
        ]
