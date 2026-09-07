from __future__ import annotations

from datetime import datetime, timezone

from leadfinder.ai.provider import parse_insights_json
from leadfinder.ai.service import assert_insights_minimized
from leadfinder.analytics import LeadFacts, build_report, period_last_days
from leadfinder.insights import (
    MIN_COMBINED_SAMPLE,
    MIN_RECOMMENDATION_SAMPLE,
    build_insights,
    confidence_label,
    evaluate_vs_baseline,
    format_uplift,
)
from leadfinder.models import Activity
from leadfinder.workflow import ActivityType

NOW = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)


def _act(place_id: str, outcome: str, created_at: str, *, act_id: int = 1) -> Activity:
    return Activity(
        id=act_id,
        place_id=place_id,
        activity_type=ActivityType.STATUS_CHANGE.value,
        created_at=created_at,
        outcome=outcome,
    )


def _lead(
    place_id: str,
    *,
    status: str,
    presence: str = "no_website",
    preset: str = "cafe",
    location: str = "Example City",
    opportunity: str = "high",
) -> LeadFacts:
    seen = "2026-08-01T12:00:00+00:00"
    activities = []
    if status in {"contacted", "interested", "won"}:
        activities.append(_act(place_id, "contacted", "2026-08-02T12:00:00+00:00"))
    if status in {"interested", "won"}:
        activities.append(
            _act(place_id, "interested", "2026-08-03T12:00:00+00:00", act_id=2)
        )
    if status == "won":
        activities.append(_act(place_id, "won", "2026-08-04T12:00:00+00:00", act_id=3))
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
        next_follow_up_at="",
        activities=tuple(activities),
    )


def _populated() -> list[LeadFacts]:
    leads: list[LeadFacts] = []
    for index in range(10):
        leads.append(_lead(f"nw-i-{index}", status="interested", presence="no_website"))
    for index in range(10):
        leads.append(_lead(f"nw-c-{index}", status="contacted", presence="no_website"))
    for index in range(4):
        leads.append(_lead(f"ws-i-{index}", status="interested", presence="has_website"))
    for index in range(16):
        leads.append(_lead(f"ws-c-{index}", status="contacted", presence="has_website"))
    for index in range(6):
        leads.append(_lead(f"unk-{index}", status="interested", presence="unknown"))
    return leads


def test_baseline_and_presence_uplift_in_percentage_points() -> None:
    leads = _populated()
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    insights = build_insights(leads, report)
    assert insights.empty is False
    assert insights.baseline.denominator >= MIN_RECOMMENDATION_SAMPLE
    assert insights.baseline.value is not None
    no_web = next(row for row in insights.ranked if row.key == "no_website")
    site = next(row for row in insights.ranked if row.key == "has_website")
    assert no_web.rate == 50.0
    assert site.rate == 20.0
    assert no_web.uplift_pp == round(no_web.rate - insights.baseline.value, 1)
    assert "pp" in format_uplift(no_web.uplift_pp)
    assert insights.strongest is not None
    assert insights.strongest.key == "no_website"
    assert insights.weakest is not None
    assert insights.weakest.key == "has_website"


def test_unknown_segments_are_not_ranked() -> None:
    leads = _populated()
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    insights = build_insights(leads, report)
    assert all(row.key != "unknown" for row in insights.ranked)
    assert all("Unknown" not in row.label for row in insights.ranked)


def test_small_samples_are_omitted() -> None:
    leads = [_lead(f"tiny-{index}", status="interested") for index in range(4)]
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    insights = build_insights(leads, report)
    assert insights.empty is True
    assert insights.strongest is None


def test_combination_requires_combined_sample() -> None:
    leads = _populated()
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    insights = build_insights(leads, report)
    assert MIN_COMBINED_SAMPLE == 8
    cafe_none = [
        row for row in insights.combinations if row.dimension == "business+presence"
    ]
    assert cafe_none
    assert all(row.n >= MIN_COMBINED_SAMPLE for row in insights.combinations)


def test_confidence_from_sample_size() -> None:
    assert confidence_label(5) == "Low"
    assert confidence_label(10) == "Medium"
    assert confidence_label(20) == "High"


def test_evaluate_vs_baseline_bands() -> None:
    from leadfinder.analytics import Rate

    baseline = Rate(numerator=24, denominator=100, value=24.0)
    assert (
        evaluate_vs_baseline(Rate(2, 4, 50.0), baseline) == "Insufficient data"
    )
    assert evaluate_vs_baseline(Rate(20, 50, 40.0), baseline) == "Above baseline"
    assert evaluate_vs_baseline(Rate(12, 50, 24.0), baseline) == "Near baseline"
    assert evaluate_vs_baseline(Rate(8, 50, 16.0), baseline) == "Below baseline"


def test_ai_payload_is_aggregates_only() -> None:
    leads = _populated()
    report = build_report(leads, period_last_days(90, now=NOW), now=NOW)
    insights = build_insights(leads, report)
    payload = insights.to_ai_payload()
    assert_insights_minimized(payload)
    blob = str(payload).lower()
    assert "place_id" not in blob
    assert "phone" not in blob
    assert "http" not in blob


def test_insights_json_parse_and_malformed() -> None:
    raw = """
    {
      "summary": "No-website cafes converted higher than baseline.",
      "observed": ["Contact to interest 50% n=20"],
      "hypotheses": ["Missing websites may correlate with interest"],
      "experiments": ["Run a focused cafe / no-website campaign"],
      "cautions": ["Do not infer causality"]
    }
    """
    parsed = parse_insights_json(raw, prompt_version="analytics_insights_v1")
    assert parsed.summary.startswith("No-website")
    assert parsed.observed
    import pytest

    from leadfinder.errors import AIResponseValidationError

    with pytest.raises(AIResponseValidationError):
        parse_insights_json("{not-json", prompt_version="analytics_insights_v1")
    with pytest.raises(AIResponseValidationError):
        parse_insights_json('{"summary":""}', prompt_version="analytics_insights_v1")
