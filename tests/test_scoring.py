from __future__ import annotations

from leadfinder.normalize import place_to_lead
from leadfinder.scoring import score_lead
from tests.conftest import synthetic_place


def _lead(**kwargs):
    return place_to_lead(
        synthetic_place("ChIJ_SYNTHETIC_020", "Score Cafe", **kwargs),
        source_query="cafe en Example City",
        location="Example City",
        search_term="cafe",
        business_preset="cafe",
        place_type="cafe",
        country="AR",
        region="",
    )


def test_high_priority_is_open_contactable_and_without_website() -> None:
    lead = score_lead(
        _lead(website="", phone="+54 11 0000", status="OPERATIONAL", user_rating_count=20)
    )
    assert lead.lead_score == 75
    assert "no website listed (+40)" in lead.lead_reason
    assert "operational (+15)" in lead.lead_reason
    assert "has phone (+10)" in lead.lead_reason
    assert "review activity (+10)" in lead.lead_reason


def test_closed_business_is_penalized_and_explained() -> None:
    lead = score_lead(
        _lead(
            website="https://example.test",
            phone="",
            status="CLOSED_PERMANENTLY",
            rating=None,
            user_rating_count=None,
        )
    )
    assert lead.lead_score == 0
    assert "closed permanently (-50)" in lead.lead_reason


def test_scoring_is_deterministic() -> None:
    first = score_lead(_lead(website="", user_rating_count=3, rating=4.0))
    second = score_lead(_lead(website="", user_rating_count=3, rating=4.0))
    assert first.lead_score == second.lead_score
    assert first.lead_reason == second.lead_reason


def test_opportunity_splits_digital_from_commercial() -> None:
    none = score_lead(
        _lead(website="", phone="+54 11 0000", status="OPERATIONAL", user_rating_count=20)
    )
    assert none.opportunity_score == 75
    assert none.opportunity_level == "high"
    assert none.digital_opportunity_score == 40
    assert "High opportunity" in none.qualification_reason

    social = _lead(
        website="https://instagram.com/cafe",
        phone="+54 11 0000",
        status="OPERATIONAL",
        user_rating_count=20,
    )
    social.website_status = "social_only"
    social = score_lead(social)
    assert social.lead_score == 55
    assert social.digital_opportunity_score == 28
    assert social.opportunity_score == 63
    assert social.opportunity_level == "medium"

