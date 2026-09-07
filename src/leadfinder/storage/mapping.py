"""Row mapping for local SQLite records."""

from __future__ import annotations

import sqlite3

from leadfinder.models import Activity, Campaign, Experiment, LocalLeadState, SearchRun


def optional_stamp(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return text


def row_to_state(row: sqlite3.Row) -> LocalLeadState:
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
        manual_priority=row["manual_priority"] if "manual_priority" in keys else "normal",
    )


def row_to_activity(row: sqlite3.Row) -> Activity:
    keys = set(row.keys())
    return Activity(
        id=int(row["id"]),
        place_id=row["place_id"],
        activity_type=row["activity_type"],
        created_at=row["created_at"],
        note=row["note"],
        contact_method=row["contact_method"],
        outcome=row["outcome"],
        metadata_json=row["metadata_json"] if "metadata_json" in keys else "",
        reverses_activity_id=int(row["reverses_activity_id"] or 0)
        if "reverses_activity_id" in keys
        else 0,
    )


def row_to_search(row: sqlite3.Row) -> SearchRun:
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
        request_count=int(row["request_count"] or 0) if "request_count" in keys else 0,
        field_profile=row["field_profile"] if "field_profile" in keys else "",
        pages=int(row["pages"] or 0) if "pages" in keys else 0,
        estimated_cost=row["estimated_cost"] if "estimated_cost" in keys else "",
        pricing_version=row["pricing_version"] if "pricing_version" in keys else "",
        currency=row["currency"] if "currency" in keys else "",
        cost_status=row["cost_status"] if "cost_status" in keys else "unknown",
        billing_sku=row["billing_sku"] if "billing_sku" in keys else "",
    )


def row_to_campaign(row: sqlite3.Row) -> Campaign:
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


def row_to_experiment(row: sqlite3.Row, campaign_ids: tuple[int, ...]) -> Experiment:
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
        campaign_ids=campaign_ids,
    )
