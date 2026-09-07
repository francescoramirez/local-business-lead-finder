"""Campaigns, search runs, and analytics facts."""

from __future__ import annotations

import sqlite3

from leadfinder.models import Activity, Campaign, SearchRun
from leadfinder.storage.mapping import row_to_campaign, row_to_search
from leadfinder.workflow import to_iso, utc_now


class CampaignsMixin:
    _conn: sqlite3.Connection

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
        commit: bool = True,
        request_count: int = 0,
        field_profile: str = "",
        pages: int = 0,
        estimated_cost: str = "",
        pricing_version: str = "",
        currency: str = "",
        cost_status: str = "unknown",
        billing_sku: str = "",
    ) -> SearchRun:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO search_runs (
                created_at, business_preset, location, region, country,
                lead_count, high_opportunity_count, campaign_id,
                request_count, field_profile, pages, estimated_cost,
                pricing_version, currency, cost_status, billing_sku
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                request_count or None,
                field_profile,
                pages,
                estimated_cost,
                pricing_version,
                currency,
                cost_status,
                billing_sku,
            ),
        )
        if commit:
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
            request_count=request_count,
            field_profile=field_profile,
            pages=pages,
            estimated_cost=estimated_cost,
            pricing_version=pricing_version,
            currency=currency,
            cost_status=cost_status,
            billing_sku=billing_sku,
        )

    def list_searches(self, *, limit: int = 20) -> list[SearchRun]:
        if limit <= 0:
            cursor = self._conn.execute(
                "SELECT * FROM search_runs ORDER BY created_at DESC, id DESC"
            )
        else:
            cursor = self._conn.execute(
                "SELECT * FROM search_runs ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            )
        return [row_to_search(row) for row in cursor.fetchall()]

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
        commit: bool = True,
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
        if commit:
            self._conn.commit()
        campaign = self.get_campaign(int(cursor.lastrowid or 0))
        assert campaign is not None
        return campaign

    def get_campaign(self, campaign_id: int) -> Campaign | None:
        row = self._conn.execute(
            "SELECT * FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        return row_to_campaign(row) if row else None

    def list_campaigns(self) -> list[Campaign]:
        cursor = self._conn.execute(
            "SELECT * FROM campaigns ORDER BY created_at DESC, id DESC"
        )
        return [row_to_campaign(row) for row in cursor.fetchall()]

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
        return row_to_campaign(row) if row else None

    def attach_leads(self, campaign_id: int, place_ids: list[str], *, commit: bool = True) -> None:
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
        if commit:
            self._conn.commit()

    def campaign_lead_ids(self, campaign_id: int) -> set[str]:
        rows = self._conn.execute(
            "SELECT place_id FROM campaign_leads WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall()
        return {row["place_id"] for row in rows}

    def load_lead_facts(self) -> list:
        from leadfinder.analytics import LeadFacts

        membership: dict[str, set[int]] = {}
        for row in self._conn.execute("SELECT campaign_id, place_id FROM campaign_leads"):
            membership.setdefault(row["place_id"], set()).add(int(row["campaign_id"]))
        grouped: dict[str, list[Activity]] = {}
        for activity in self.list_all_activities():  # type: ignore[attr-defined]
            grouped.setdefault(activity.place_id, []).append(activity)
        facts: list[LeadFacts] = []
        for state in self.list_all():  # type: ignore[attr-defined]
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
