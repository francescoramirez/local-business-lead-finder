from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from leadfinder.analytics import (
    MIN_RATE_SAMPLE,
    LeadFacts,
    build_report,
    compare_reports,
    format_rate,
    historical_flags,
    in_period,
    period_custom,
    period_last_days,
)
from leadfinder.application.service import LeadService
from leadfinder.models import Activity
from leadfinder.storage.local_leads import LocalLeadStore
from leadfinder.workflow import ActivityType

NOW = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)


def _act(
    place_id: str,
    activity_type: str,
    created_at: str,
    *,
    outcome: str = "",
    method: str = "",
    note: str = "",
    act_id: int = 1,
) -> Activity:
    return Activity(
        id=act_id,
        place_id=place_id,
        activity_type=activity_type,
        created_at=created_at,
        note=note,
        contact_method=method,
        outcome=outcome,
    )


def _lead(
    place_id: str,
    *,
    seen: str,
    status: str = "new",
    preset: str = "cafe",
    location: str = "Example City",
    presence: str = "no_website",
    opportunity: str = "high",
    activities: tuple[Activity, ...] = (),
    campaigns: frozenset[int] = frozenset(),
    follow: str = "",
) -> LeadFacts:
    return LeadFacts(
        place_id=place_id,
        first_seen_at=seen,
        contact_status=status,
        opportunity_level=opportunity,
        website_status=presence,
        business_preset=preset,
        location=location,
        region="Example",
        country="AR",
        next_follow_up_at=follow,
        activities=activities,
        campaign_ids=campaigns,
    )


def test_contacted_once_from_events_and_skip_stage() -> None:
    seen = "2026-08-01T12:00:00+00:00"
    won_at = "2026-08-10T12:00:00+00:00"
    lead = _lead(
        "p1",
        seen=seen,
        status="won",
        activities=(
            _act("p1", ActivityType.STATUS_CHANGE.value, won_at, outcome="won"),
        ),
    )
    contacted, interested, won, fallback = historical_flags(lead)
    assert contacted is True
    assert interested is True
    assert won is True
    assert fallback is False


def test_won_still_counts_as_historically_contacted_when_snapshot_moved_back() -> None:
    lead = _lead(
        "p2",
        seen="2026-08-01T12:00:00+00:00",
        status="new",
        activities=(
            _act(
                "p2",
                ActivityType.STATUS_CHANGE.value,
                "2026-08-02T12:00:00+00:00",
                outcome="contacted",
            ),
            _act(
                "p2",
                ActivityType.STATUS_CHANGE.value,
                "2026-08-03T12:00:00+00:00",
                outcome="new",
                act_id=2,
            ),
        ),
    )
    contacted, _i, _w, fallback = historical_flags(lead)
    assert contacted is True
    assert fallback is False


def test_current_won_status_counts_historically_as_contacted_and_interested() -> None:
    lead = _lead("p-won", seen="2026-08-01T12:00:00+00:00", status="won")
    contacted, interested, won, fallback = historical_flags(lead)
    assert contacted is True
    assert interested is True
    assert won is True
    assert fallback is True


def test_rejected_without_activity_is_not_contacted() -> None:
    lead = _lead("p3", seen="2026-08-01T12:00:00+00:00", status="rejected")
    contacted, interested, won, fallback = historical_flags(lead)
    assert contacted is False
    assert interested is False
    assert won is False
    assert fallback is False


def test_status_fallback_for_old_interested_lead() -> None:
    lead = _lead("p4", seen="2026-08-01T12:00:00+00:00", status="interested")
    contacted, interested, won, fallback = historical_flags(lead)
    assert contacted is True
    assert interested is True
    assert won is False
    assert fallback is True


def test_rates_and_minimum_sample() -> None:
    leads = []
    for index in range(3):
        leads.append(
            _lead(
                f"c{index}",
                seen="2026-08-20T12:00:00+00:00",
                status="contacted",
                activities=(
                    _act(
                        f"c{index}",
                        ActivityType.STATUS_CHANGE.value,
                        "2026-08-21T12:00:00+00:00",
                        outcome="contacted",
                    ),
                ),
            )
        )
    for index in range(3):
        leads.append(
            _lead(
                f"i{index}",
                seen="2026-08-20T12:00:00+00:00",
                status="interested",
                activities=(
                    _act(
                        f"i{index}",
                        ActivityType.STATUS_CHANGE.value,
                        "2026-08-21T12:00:00+00:00",
                        outcome="contacted",
                    ),
                    _act(
                        f"i{index}",
                        ActivityType.STATUS_CHANGE.value,
                        "2026-08-22T12:00:00+00:00",
                        outcome="interested",
                        act_id=2,
                    ),
                ),
            )
        )
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    assert report.historical.total_leads == 6
    assert report.historical.contacted_once == 6
    assert report.historical.interested_once == 3
    assert report.contact_to_interest.value == 50.0
    tiny = build_report(leads[:2], period_last_days(90, now=NOW), now=NOW)
    assert tiny.contact_rate.value is None
    assert format_rate(tiny.contact_rate) == "Not enough data"
    assert MIN_RATE_SAMPLE == 3


def test_zero_denominator() -> None:
    lead = _lead("n1", seen="2026-08-20T12:00:00+00:00", status="new")
    report = build_report([lead], period_last_days(90, now=NOW), now=NOW)
    assert report.contact_to_interest.denominator == 0
    assert report.contact_to_interest.value is None
    assert report.contact_to_win.value is None


def test_period_filters_and_timezone_boundary() -> None:
    inside = _lead("in", seen="2026-08-31T03:00:00+00:00")
    outside = _lead("out", seen="2026-08-29T12:00:00+00:00")
    period = period_last_days(7, now=NOW)
    assert in_period(inside.first_seen_at, period)
    assert not in_period(outside.first_seen_at, period)
    custom = period_custom(
        datetime(2026, 8, 30, tzinfo=timezone.utc),
        datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    report = build_report([inside, outside], custom, now=NOW)
    assert report.historical.total_leads == 1


def test_segments_business_presence_location_method() -> None:
    leads = [
        _lead(
            "a",
            seen="2026-08-20T12:00:00+00:00",
            preset="cafe",
            presence="no_website",
            location="Mar del Plata",
            status="interested",
            activities=(
                _act(
                    "a",
                    ActivityType.CONTACT_ATTEMPT.value,
                    "2026-08-21T12:00:00+00:00",
                    method="phone",
                ),
                _act(
                    "a",
                    ActivityType.STATUS_CHANGE.value,
                    "2026-08-22T12:00:00+00:00",
                    outcome="interested",
                    act_id=2,
                ),
            ),
            campaigns=frozenset({1}),
        ),
        _lead(
            "b",
            seen="2026-08-20T12:00:00+00:00",
            preset="gym",
            presence="social_only",
            location="Córdoba",
            status="contacted",
            activities=(
                _act(
                    "b",
                    ActivityType.CONTACT_ATTEMPT.value,
                    "2026-08-21T12:00:00+00:00",
                    method="instagram",
                ),
            ),
            campaigns=frozenset({2}),
        ),
    ]
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    business = {row.key: row for row in report.by_business}
    assert business["cafe"].interested == 1
    presence = {row.key: row for row in report.by_presence}
    assert presence["no_website"].leads == 1
    locations = {row.key: row for row in report.by_location}
    assert "Mar del Plata" in locations
    methods = {row.key: row for row in report.by_method}
    assert methods["phone"].leads == 1
    assert methods["instagram"].leads == 1
    cafe_only = build_report(leads, period_last_days(90, now=NOW), campaign_id=1, now=NOW)
    assert cafe_only.historical.total_leads == 1


def test_median_time_to_contact() -> None:
    leads = []
    for index, days in enumerate((1, 2, 10)):
        seen = "2026-08-01T12:00:00+00:00"
        contacted = (
            datetime(2026, 8, 1, 12, tzinfo=timezone.utc) + timedelta(days=days)
        ).isoformat()
        leads.append(
            _lead(
                f"t{index}",
                seen=seen,
                status="contacted",
                activities=(
                    _act(
                        f"t{index}",
                        ActivityType.STATUS_CHANGE.value,
                        contacted,
                        outcome="contacted",
                    ),
                ),
            )
        )
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    assert report.time_to_first_contact.n == 3
    assert report.time_to_first_contact.median_days == 2.0


def test_campaign_store_and_export(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "a.db")
    service = LeadService(store)
    campaign = service.create_campaign(
        name="Cafes Example City",
        business_preset="cafe",
        location="Example City",
        notes="Social-only first.",
    )
    store.mark_seen(
        "ChIJ_SYNTHETIC_A1",
        seen_at="2026-08-20T12:00:00+00:00",
        business_preset="cafe",
        source_location="Example City",
        website_status="social_only",
        opportunity_level="high",
        campaign_id=campaign.id,
    )
    store.attach_leads(campaign.id, ["ChIJ_SYNTHETIC_A1"])
    store.set_contact_status("ChIJ_SYNTHETIC_A1", "contacted", now=NOW)
    store.set_contact_status("ChIJ_SYNTHETIC_A1", "interested", now=NOW + timedelta(days=1))
    store.set_contact_status("ChIJ_SYNTHETIC_A1", "won", now=NOW + timedelta(days=2))
    report = service.analytics_report(days=90, campaign_id=campaign.id, now=NOW + timedelta(days=3))
    assert report.historical.won_once == 1
    assert report.historical.contacted_once == 1
    json_path = service.export_analytics(report, tmp_path / "report.json")
    csv_path = service.export_analytics(report, tmp_path / "report.csv")
    md_path = service.export_analytics(report, tmp_path / "campaign-report.md")
    assert "contacted_once" in json_path.read_text(encoding="utf-8")
    assert "overview" in csv_path.read_text(encoding="utf-8")
    assert "# Campaign Report" in md_path.read_text(encoding="utf-8")
    other = service.create_campaign(name="Dentists", business_preset="dentist", location="Córdoba")
    left = service.analytics_report(days=0, campaign_id=campaign.id, now=NOW)
    right = service.analytics_report(days=0, campaign_id=other.id, now=NOW)
    rows = compare_reports(left, right)
    assert rows[0][0] == "Leads"
    assert rows[0][1] == "1"
    store.close()
    restored = LocalLeadStore(tmp_path / "a.db")
    again = LeadService(restored).analytics_report(
        days=90, campaign_id=campaign.id, now=NOW + timedelta(days=3)
    )
    assert again.historical.won_once == report.historical.won_once
    restored.close()


def test_synthetic_three_campaigns(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "multi.db")
    service = LeadService(store)
    specs = [
        ("Cafes Mar del Plata", "cafe", "Mar del Plata", "no_website"),
        ("Dentists Cordoba", "dentist", "Córdoba", "social_only"),
        ("Gyms Rosario", "gym", "Rosario", "has_website"),
    ]
    for name, preset, city, presence in specs:
        campaign = service.create_campaign(name=name, business_preset=preset, location=city)
        for index in range(10):
            place_id = f"ChIJ_{preset}_{index}"
            store.mark_seen(
                place_id,
                seen_at="2026-08-10T12:00:00+00:00",
                label=f"{preset} {index}",
                business_preset=preset,
                source_location=city,
                website_status=presence,
                opportunity_level="high" if index < 4 else "medium",
                campaign_id=campaign.id,
            )
            store.attach_leads(campaign.id, [place_id])
            if index < 6:
                store.set_contact_status(place_id, "contacted", now=NOW)
            if index < 3:
                store.set_contact_status(place_id, "interested", now=NOW + timedelta(hours=2))
            if index < 1:
                store.set_contact_status(place_id, "won", now=NOW + timedelta(days=1))
    report = service.analytics_report(days=90, now=NOW + timedelta(days=2))
    assert report.historical.total_leads == 30
    assert report.historical.contacted_once == 18
    assert report.historical.interested_once == 9
    assert report.historical.won_once == 3
    assert any(row.key == "cafe" for row in report.by_business)
    assert any(row.key == "no_website" for row in report.by_presence)
    cafe = next(item for item in service.campaigns() if item.name.startswith("Cafes"))
    filtered = service.analytics_report(days=90, campaign_id=cafe.id, now=NOW + timedelta(days=2))
    assert filtered.historical.total_leads == 10
    store.close()
