"""Workspace ZIP merge into the local database."""

from __future__ import annotations

import sqlite3

from leadfinder.storage.leads import LEAD_COLUMNS
from leadfinder.storage.mapping import optional_stamp
from leadfinder.workflow import to_iso, utc_now


class WorkspaceMixin:
    _conn: sqlite3.Connection

    def merge_workspace(
        self,
        *,
        workflow: list[dict],
        campaigns: list[dict],
        activities: list[dict],
        experiments: list[dict],
    ) -> dict[str, int]:
        added = {"leads": 0, "campaigns": 0, "activities": 0, "experiments": 0, "skipped_leads": 0}
        with self.transaction():  # type: ignore[attr-defined]
            campaign_map: dict[int, int] = {}
            by_name = {item.name.lower(): item for item in self.list_campaigns()}  # type: ignore[attr-defined]
            for campaign in campaigns:
                old_id = int(campaign.get("id") or 0)
                name = str(campaign.get("name") or "").strip()
                if not name:
                    continue
                existing = by_name.get(name.lower())
                if existing is None:
                    created = self.create_campaign(  # type: ignore[attr-defined]
                        name=name,
                        business_preset=str(campaign.get("business_preset") or ""),
                        location=str(campaign.get("location") or ""),
                        region=str(campaign.get("region") or ""),
                        country=str(campaign.get("country") or ""),
                        notes=str(campaign.get("notes") or ""),
                        auto_created=bool(campaign.get("auto_created")),
                        local_day=str(campaign.get("local_day") or ""),
                        created_at=optional_stamp(campaign.get("created_at")),
                        commit=False,
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
                if self.get(place_id) is not None:  # type: ignore[attr-defined]
                    added["skipped_leads"] += 1
                    continue
                self._insert_imported_lead(row, campaign_map)
                added["leads"] += 1
            existing_acts = {
                (item.place_id, item.created_at, item.activity_type, item.outcome)
                for item in self.list_all_activities()  # type: ignore[attr-defined]
            }
            for activity in activities:
                place_id = str(activity.get("place_id") or "")
                if self.get(place_id) is None:  # type: ignore[attr-defined]
                    continue
                key = (
                    place_id,
                    str(activity.get("created_at") or ""),
                    str(activity.get("activity_type") or ""),
                    str(activity.get("outcome") or ""),
                )
                if key in existing_acts:
                    continue
                self.add_activity(  # type: ignore[attr-defined]
                    place_id,
                    str(activity.get("activity_type") or "note"),
                    note=str(activity.get("note") or ""),
                    contact_method=str(activity.get("contact_method") or ""),
                    outcome=str(activity.get("outcome") or ""),
                    created_at=optional_stamp(activity.get("created_at")),
                    commit=False,
                )
                existing_acts.add(key)
                added["activities"] += 1
            for experiment in experiments:
                imported = self.create_experiment(  # type: ignore[attr-defined]
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
                    created_at=optional_stamp(experiment.get("created_at")),
                    commit=False,
                )
                raw_ids = experiment.get("campaign_ids") or ()
                mapped = [
                    campaign_map[int(item)]
                    for item in raw_ids
                    if int(item) in campaign_map
                ]
                if mapped:
                    self.attach_campaigns(imported.id, mapped, commit=False)  # type: ignore[attr-defined]
                added["experiments"] += 1
        return added

    def _insert_imported_lead(self, row: dict, campaign_map: dict[int, int]) -> None:
        old_campaign = int(row.get("campaign_id") or 0)
        campaign_id = campaign_map.get(old_campaign, 0)
        now = str(row.get("first_seen_at") or to_iso(utc_now()))
        priority = str(row.get("manual_priority") or "normal")
        self._conn.execute(
            f"""
            INSERT INTO leads_local ({LEAD_COLUMNS})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                priority,
            ),
        )
        if campaign_id:
            self.attach_leads(  # type: ignore[attr-defined]
                campaign_id, [str(row.get("place_id") or "")], commit=False
            )
