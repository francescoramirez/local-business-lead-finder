from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from leadfinder.errors import BackupError, DatabaseError, RestoreError, WorkspaceError
from leadfinder.models import Activity, Campaign, Experiment, LocalLeadState, SearchRun
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
        business_preset=row["business_preset"] if "business_preset" in keys else "",
        source_location=row["source_location"] if "source_location" in keys else "",
        region=row["region"] if "region" in keys else "",
        country=row["country"] if "country" in keys else "",
        website_status=row["website_status"] if "website_status" in keys else "",
        campaign_id=int(row["campaign_id"] or 0) if "campaign_id" in keys else 0,
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


def _row_to_search(row: sqlite3.Row) -> SearchRun:
    keys = set(row.keys())
    return SearchRun(
        id=int(row["id"]),
        created_at=row["created_at"],
        business_preset=row["business_preset"],
        location=row["location"],
        region=row["region"],
        country=row["country"],
        lead_count=int(row["lead_count"]),
        high_opportunity_count=int(row["high_opportunity_count"]),
        campaign_id=int(row["campaign_id"] or 0) if "campaign_id" in keys else 0,
    )


def _row_to_campaign(row: sqlite3.Row) -> Campaign:
    return Campaign(
        id=int(row["id"]),
        name=row["name"],
        created_at=row["created_at"],
        notes=row["notes"],
        business_preset=row["business_preset"],
        location=row["location"],
        region=row["region"],
        country=row["country"],
        auto_created=bool(row["auto_created"]),
        local_day=row["local_day"],
    )


def _optional_stamp(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return text


class LocalLeadStore:
    """SQLite store for user-generated lead metadata only (not Places content)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            migrate(self._conn)
        except sqlite3.DatabaseError as error:
            raise DatabaseError(
                "The local LeadFinder database could not be opened. "
                "It may be damaged. Restore a backup with File > Restore data, "
                "or run: leadfinder doctor"
            ) from error

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
                """
                INSERT INTO leads_local (
                    place_id, contact_status, notes, first_seen_at, last_seen_at,
                    last_contacted_at, tags, next_follow_up_at, last_activity_at,
                    label, opportunity_level, opportunity_score, has_phone,
                    business_preset, source_location, region, country, website_status,
                    campaign_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            outcome=status,
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
        campaign_id: int = 0,
    ) -> SearchRun:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO search_runs (
                created_at, business_preset, location, region, country,
                lead_count, high_opportunity_count, campaign_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stamp,
                business_preset,
                location,
                region,
                country,
                lead_count,
                high_opportunity_count,
                campaign_id or None,
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
            campaign_id=campaign_id,
        )

    def list_searches(self, *, limit: int = 20) -> list[SearchRun]:
        cursor = self._conn.execute(
            "SELECT * FROM search_runs ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
        return [_row_to_search(row) for row in cursor.fetchall()]

    def create_campaign(
        self,
        *,
        name: str,
        business_preset: str = "",
        location: str = "",
        region: str = "",
        country: str = "",
        notes: str = "",
        auto_created: bool = False,
        local_day: str = "",
        created_at: str | None = None,
    ) -> Campaign:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO campaigns (
                name, created_at, notes, business_preset, location, region, country,
                auto_created, local_day
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                stamp,
                notes,
                business_preset,
                location,
                region,
                country,
                int(auto_created),
                local_day,
            ),
        )
        self._conn.commit()
        campaign = self.get_campaign(int(cursor.lastrowid or 0))
        assert campaign is not None
        return campaign

    def get_campaign(self, campaign_id: int) -> Campaign | None:
        row = self._conn.execute(
            "SELECT * FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        return _row_to_campaign(row) if row else None

    def list_campaigns(self) -> list[Campaign]:
        cursor = self._conn.execute(
            "SELECT * FROM campaigns ORDER BY created_at DESC, id DESC"
        )
        return [_row_to_campaign(row) for row in cursor.fetchall()]

    def set_campaign_notes(self, campaign_id: int, notes: str) -> Campaign:
        self._conn.execute(
            "UPDATE campaigns SET notes = ? WHERE id = ?",
            (notes, campaign_id),
        )
        self._conn.commit()
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError(f"Unknown campaign: {campaign_id}")
        return campaign

    def find_auto_campaign(
        self,
        *,
        business_preset: str,
        location: str,
        region: str,
        country: str,
        local_day: str,
    ) -> Campaign | None:
        row = self._conn.execute(
            """
            SELECT * FROM campaigns
            WHERE auto_created = 1 AND business_preset = ? AND location = ?
              AND region = ? AND country = ? AND local_day = ?
            ORDER BY id DESC LIMIT 1
            """,
            (business_preset, location, region, country, local_day),
        ).fetchone()
        return _row_to_campaign(row) if row else None

    def attach_leads(self, campaign_id: int, place_ids: list[str]) -> None:
        for place_id in place_ids:
            if not place_id:
                continue
            self._conn.execute(
                """
                INSERT OR IGNORE INTO campaign_leads (campaign_id, place_id)
                VALUES (?, ?)
                """,
                (campaign_id, place_id),
            )
            self._conn.execute(
                "UPDATE leads_local SET campaign_id = ? WHERE place_id = ?",
                (campaign_id, place_id),
            )
        self._conn.commit()

    def campaign_lead_ids(self, campaign_id: int) -> set[str]:
        rows = self._conn.execute(
            "SELECT place_id FROM campaign_leads WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall()
        return {row["place_id"] for row in rows}

    def list_all_activities(self) -> list[Activity]:
        cursor = self._conn.execute(
            "SELECT * FROM activities ORDER BY created_at ASC, id ASC"
        )
        return [_row_to_activity(row) for row in cursor.fetchall()]

    def load_lead_facts(self) -> list:
        from leadfinder.analytics import LeadFacts

        membership: dict[str, set[int]] = {}
        for row in self._conn.execute("SELECT campaign_id, place_id FROM campaign_leads"):
            membership.setdefault(row["place_id"], set()).add(int(row["campaign_id"]))
        grouped: dict[str, list[Activity]] = {}
        for activity in self.list_all_activities():
            grouped.setdefault(activity.place_id, []).append(activity)
        facts: list[LeadFacts] = []
        for state in self.list_all():
            ids = membership.get(state.place_id, set())
            if state.campaign_id:
                ids.add(state.campaign_id)
            facts.append(
                LeadFacts(
                    place_id=state.place_id,
                    first_seen_at=state.first_seen_at,
                    contact_status=state.contact_status,
                    opportunity_level=state.opportunity_level,
                    website_status=state.website_status,
                    business_preset=state.business_preset,
                    location=state.source_location,
                    region=state.region,
                    country=state.country,
                    next_follow_up_at=state.next_follow_up_at,
                    activities=tuple(grouped.get(state.place_id, ())),
                    campaign_ids=frozenset(ids),
                )
            )
        return facts

    def delete_prospect(self, place_id: str) -> None:
        with self.transaction():
            self._conn.execute("DELETE FROM campaign_leads WHERE place_id = ?", (place_id,))
            self._conn.execute("DELETE FROM activities WHERE place_id = ?", (place_id,))
            self._conn.execute("DELETE FROM leads_local WHERE place_id = ?", (place_id,))

    def pipeline_rows(self) -> list[tuple[str, str, str]]:
        return [
            (item.contact_status, item.next_follow_up_at, item.opportunity_level)
            for item in self.list_all()
        ]

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

    def restore(self, source: Path) -> Path:
        source = Path(source)
        if not source.exists():
            raise RestoreError("Backup file not found.")
        validate_leadfinder_db(source)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safety = self.path.with_name(f"leadfinder-pre-restore-{stamp}.db")
        self.backup(safety)
        self._conn.close()
        try:
            for extra in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
                if extra != self.path and extra.exists():
                    extra.unlink()
            import shutil

            shutil.copy2(source, self.path)
            self._open()
        except (OSError, sqlite3.Error, DatabaseError) as error:
            try:
                import shutil

                shutil.copy2(safety, self.path)
                self._open()
            except Exception:
                pass
            raise RestoreError(
                "Could not restore the backup. A safety copy of the previous database "
                f"was saved to {safety}."
            ) from error
        return safety

    def _open(self) -> None:
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        migrate(self._conn)

    def create_experiment(
        self,
        *,
        name: str,
        hypothesis: str = "",
        status: str = "draft",
        business_preset: str = "",
        location: str = "",
        digital_presence: str = "",
        opportunity_level: str = "",
        target_metric: str = "contact_to_interest",
        notes: str = "",
        observations: str = "",
        conclusion: str = "",
        created_at: str | None = None,
    ) -> Experiment:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO experiments (
                name, created_at, status, hypothesis, business_preset, location,
                digital_presence, opportunity_level, target_metric, notes,
                observations, conclusion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                stamp,
                status,
                hypothesis,
                business_preset,
                location,
                digital_presence,
                opportunity_level,
                target_metric,
                notes,
                observations,
                conclusion,
            ),
        )
        self._conn.commit()
        found = self.get_experiment(int(cursor.lastrowid or 0))
        assert found is not None
        return found

    def get_experiment(self, experiment_id: int) -> Experiment | None:
        row = self._conn.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            return None
        return self._experiment_from_row(row)

    def list_experiments(self) -> list[Experiment]:
        cursor = self._conn.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC, id DESC"
        )
        return [self._experiment_from_row(row) for row in cursor.fetchall()]

    def update_experiment(
        self,
        experiment_id: int,
        *,
        name: str | None = None,
        status: str | None = None,
        hypothesis: str | None = None,
        notes: str | None = None,
        observations: str | None = None,
        conclusion: str | None = None,
        business_preset: str | None = None,
        location: str | None = None,
        digital_presence: str | None = None,
        opportunity_level: str | None = None,
    ) -> Experiment:
        current = self.get_experiment(experiment_id)
        if current is None:
            raise WorkspaceError(f"Unknown experiment: {experiment_id}")
        self._conn.execute(
            """
            UPDATE experiments SET
                name = ?, status = ?, hypothesis = ?, notes = ?,
                observations = ?, conclusion = ?, business_preset = ?,
                location = ?, digital_presence = ?, opportunity_level = ?
            WHERE id = ?
            """,
            (
                current.name if name is None else name,
                current.status if status is None else status,
                current.hypothesis if hypothesis is None else hypothesis,
                current.notes if notes is None else notes,
                current.observations if observations is None else observations,
                current.conclusion if conclusion is None else conclusion,
                current.business_preset if business_preset is None else business_preset,
                current.location if location is None else location,
                current.digital_presence if digital_presence is None else digital_presence,
                current.opportunity_level if opportunity_level is None else opportunity_level,
                experiment_id,
            ),
        )
        self._conn.commit()
        found = self.get_experiment(experiment_id)
        assert found is not None
        return found

    def attach_campaigns(self, experiment_id: int, campaign_ids: list[int]) -> None:
        for campaign_id in campaign_ids:
            if not campaign_id:
                continue
            self._conn.execute(
                """
                INSERT OR IGNORE INTO experiment_campaigns (experiment_id, campaign_id)
                VALUES (?, ?)
                """,
                (experiment_id, campaign_id),
            )
        self._conn.commit()

    def experiment_campaign_ids(self, experiment_id: int) -> frozenset[int]:
        rows = self._conn.execute(
            "SELECT campaign_id FROM experiment_campaigns WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchall()
        return frozenset(int(row["campaign_id"]) for row in rows)

    def _experiment_from_row(self, row: sqlite3.Row) -> Experiment:
        return Experiment(
            id=int(row["id"]),
            name=row["name"],
            created_at=row["created_at"],
            status=row["status"],
            hypothesis=row["hypothesis"],
            business_preset=row["business_preset"],
            location=row["location"],
            digital_presence=row["digital_presence"],
            opportunity_level=row["opportunity_level"],
            target_metric=row["target_metric"],
            notes=row["notes"],
            observations=row["observations"],
            conclusion=row["conclusion"],
            campaign_ids=tuple(sorted(self.experiment_campaign_ids(int(row["id"])))),
        )

    def merge_workspace(
        self,
        *,
        workflow: list[dict],
        campaigns: list[dict],
        activities: list[dict],
        experiments: list[dict],
    ) -> dict[str, int]:
        added = {"leads": 0, "campaigns": 0, "activities": 0, "experiments": 0, "skipped_leads": 0}
        campaign_map: dict[int, int] = {}
        by_name = {item.name.lower(): item for item in self.list_campaigns()}
        for campaign in campaigns:
            old_id = int(campaign.get("id") or 0)
            name = str(campaign.get("name") or "").strip()
            if not name:
                continue
            existing = by_name.get(name.lower())
            if existing is None:
                created = self.create_campaign(
                    name=name,
                    business_preset=str(campaign.get("business_preset") or ""),
                    location=str(campaign.get("location") or ""),
                    region=str(campaign.get("region") or ""),
                    country=str(campaign.get("country") or ""),
                    notes=str(campaign.get("notes") or ""),
                    auto_created=bool(campaign.get("auto_created")),
                    local_day=str(campaign.get("local_day") or ""),
                    created_at=_optional_stamp(campaign.get("created_at")),
                )
                by_name[name.lower()] = created
                added["campaigns"] += 1
                campaign_map[old_id] = created.id
            else:
                campaign_map[old_id] = existing.id
        for row in workflow:
            place_id = str(row.get("place_id") or "").strip()
            if not place_id:
                continue
            if self.get(place_id) is not None:
                added["skipped_leads"] += 1
                continue
            self._insert_imported_lead(row, campaign_map)
            added["leads"] += 1
        existing_acts = {
            (item.place_id, item.created_at, item.activity_type, item.outcome)
            for item in self.list_all_activities()
        }
        for activity in activities:
            place_id = str(activity.get("place_id") or "")
            if self.get(place_id) is None:
                continue
            key = (
                place_id,
                str(activity.get("created_at") or ""),
                str(activity.get("activity_type") or ""),
                str(activity.get("outcome") or ""),
            )
            if key in existing_acts:
                continue
            self.add_activity(
                place_id,
                str(activity.get("activity_type") or "note"),
                note=str(activity.get("note") or ""),
                contact_method=str(activity.get("contact_method") or ""),
                outcome=str(activity.get("outcome") or ""),
                created_at=_optional_stamp(activity.get("created_at")),
            )
            existing_acts.add(key)
            added["activities"] += 1
        for experiment in experiments:
            imported = self.create_experiment(
                name=str(experiment.get("name") or "Imported experiment"),
                hypothesis=str(experiment.get("hypothesis") or ""),
                status=str(experiment.get("status") or "draft"),
                business_preset=str(experiment.get("business_preset") or ""),
                location=str(experiment.get("location") or ""),
                digital_presence=str(experiment.get("digital_presence") or ""),
                opportunity_level=str(experiment.get("opportunity_level") or ""),
                target_metric=str(experiment.get("target_metric") or "contact_to_interest"),
                notes=str(experiment.get("notes") or ""),
                observations=str(experiment.get("observations") or ""),
                conclusion=str(experiment.get("conclusion") or ""),
                created_at=_optional_stamp(experiment.get("created_at")),
            )
            raw_ids = experiment.get("campaign_ids") or ()
            mapped = [
                campaign_map[int(item)]
                for item in raw_ids
                if int(item) in campaign_map
            ]
            if mapped:
                self.attach_campaigns(imported.id, mapped)
            added["experiments"] += 1
        return added

    def _insert_imported_lead(self, row: dict, campaign_map: dict[int, int]) -> None:
        old_campaign = int(row.get("campaign_id") or 0)
        campaign_id = campaign_map.get(old_campaign, 0)
        now = str(row.get("first_seen_at") or to_iso(utc_now()))
        self._conn.execute(
            """
            INSERT INTO leads_local (
                place_id, contact_status, notes, first_seen_at, last_seen_at,
                last_contacted_at, tags, next_follow_up_at, last_activity_at,
                label, opportunity_level, opportunity_score, has_phone,
                business_preset, source_location, region, country, website_status,
                campaign_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row.get("place_id") or ""),
                str(row.get("contact_status") or "new"),
                str(row.get("notes") or ""),
                now,
                str(row.get("last_seen_at") or now),
                str(row.get("last_contacted_at") or ""),
                str(row.get("tags") or ""),
                str(row.get("next_follow_up_at") or ""),
                str(row.get("last_activity_at") or ""),
                str(row.get("label") or ""),
                str(row.get("opportunity_level") or ""),
                int(row.get("opportunity_score") or 0),
                int(bool(row.get("has_phone"))),
                str(row.get("business_preset") or ""),
                str(row.get("source_location") or ""),
                str(row.get("region") or ""),
                str(row.get("country") or ""),
                str(row.get("website_status") or ""),
                campaign_id or None,
            ),
        )
        if campaign_id:
            self.attach_leads(campaign_id, [str(row.get("place_id") or "")])
        else:
            self._conn.commit()


def validate_leadfinder_db(path: Path) -> int:
    from leadfinder.storage.schema import _table_exists

    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise RestoreError("Backup file is not a valid SQLite database.") from error
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row is None or str(row[0]).lower() != "ok":
            raise RestoreError("Backup failed SQLite integrity check.")
        if not _table_exists(conn, "leads_local") and not _table_exists(conn, "schema_meta"):
            raise RestoreError("File is not a LeadFinder database.")
        return schema_version(conn)
    except sqlite3.Error as error:
        raise RestoreError("Backup file is not a valid SQLite database.") from error
    finally:
        conn.close()
