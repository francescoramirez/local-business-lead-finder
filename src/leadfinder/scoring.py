from __future__ import annotations

from leadfinder.digital_presence import derived_tags
from leadfinder.filtering import CLOSED_PERMANENTLY, CLOSED_TEMPORARILY, annotate_flags
from leadfinder.models import Lead

# Deterministic, documented scoring for a web-agency outreach list.
# Rating/review fields are included only when the request already uses the
# Enterprise field profile required for websiteUri.
SCORE_NO_WEBSITE = 40
SCORE_WEAK_WEB_PRESENCE = 20
SCORE_OPERATIONAL = 15
SCORE_PHONE = 10
SCORE_ACTIVE_REVIEWS = 10
SCORE_SOME_REVIEWS = 5
PENALTY_CLOSED_PERMANENTLY = 50
PENALTY_CLOSED_TEMPORARILY = 20
WEAK_WEB_STATUSES = {
    "social_only",
    "link_aggregator",
    "unreachable",
    "non_https",
    "parked",
    "weak_website",
}

# Digital-opportunity points are separate from lead_score so the two numbers
# stay explainable. lead_score keeps the original +40 / +20 website weights.
DIGITAL_OPPORTUNITY_POINTS = {
    "no_website": 40,
    "parked": 32,
    "social_only": 28,
    "link_aggregator": 26,
    "weak_website": 22,
    "unreachable": 20,
    "non_https": 18,
    "unknown": 0,
    "has_website": 0,
}

HIGH_OPPORTUNITY_MIN = 70
MEDIUM_OPPORTUNITY_MIN = 45

OPPORTUNITY_LABELS = {
    "high": "High opportunity",
    "medium": "Medium opportunity",
    "low": "Low opportunity",
}


def _opportunity_level(score: int) -> str:
    if score >= HIGH_OPPORTUNITY_MIN:
        return "high"
    if score >= MEDIUM_OPPORTUNITY_MIN:
        return "medium"
    return "low"


def _plain_digital_reason(status: str) -> str:
    return {
        "no_website": "No website detected",
        "parked": "Listed website looks parked or placeholder",
        "social_only": "Business uses a social profile as its website",
        "link_aggregator": "Business uses a link-in-bio page as its website",
        "weak_website": "Website looks extremely thin",
        "unreachable": "Listed website could not be reached",
        "non_https": "Website is HTTP-only",
        "has_website": "Standalone website present",
    }.get(status, "")


def score_lead(lead: Lead) -> Lead:
    annotate_flags(lead)
    commercial = 0
    digital_legacy = 0
    reasons: list[str] = []
    plain: list[str] = []

    status = (lead.business_status or "").upper()
    if status == CLOSED_PERMANENTLY:
        commercial -= PENALTY_CLOSED_PERMANENTLY
        reasons.append("closed permanently (-50)")
        plain.append("closed permanently")
    elif status == CLOSED_TEMPORARILY:
        commercial -= PENALTY_CLOSED_TEMPORARILY
        reasons.append("closed temporarily (-20)")
        plain.append("closed temporarily")
    elif lead.operational:
        commercial += SCORE_OPERATIONAL
        reasons.append("operational (+15)")
        plain.append("business is operational")

    if not lead.has_website:
        digital_legacy = SCORE_NO_WEBSITE
        reasons.append("no website listed (+40)")
    elif lead.website_status in WEAK_WEB_STATUSES:
        digital_legacy = SCORE_WEAK_WEB_PRESENCE
        reasons.append(f"{lead.website_status.replace('_', ' ')} (+20)")

    digital_reason = _plain_digital_reason(lead.website_status)
    if digital_reason:
        plain.append(digital_reason)

    if lead.contactable:
        commercial += SCORE_PHONE
        reasons.append("has phone (+10)")
        plain.append("phone available")

    reviews = lead.user_rating_count or 0
    if reviews >= 10:
        commercial += SCORE_ACTIVE_REVIEWS
        reasons.append("review activity (+10)")
        plain.append(f"{reviews} Google reviews")
    elif reviews >= 1 or lead.rating is not None:
        commercial += SCORE_SOME_REVIEWS
        reasons.append("some public reviews (+5)")
        if reviews:
            plain.append(f"{reviews} Google reviews")
        else:
            plain.append("some public reviews")

    lead.digital_opportunity_score = DIGITAL_OPPORTUNITY_POINTS.get(lead.website_status, 0)
    lead.lead_score = max(0, min(100, commercial + digital_legacy))
    lead.opportunity_score = max(0, min(100, commercial + lead.digital_opportunity_score))
    lead.opportunity_level = _opportunity_level(lead.opportunity_score)
    lead.lead_reason = "; ".join(reasons) if reasons else "no scoring signals"
    label = OPPORTUNITY_LABELS[lead.opportunity_level]
    lead.qualification_reason = f"{label}: {', '.join(plain)}." if plain else f"{label}."
    lead.derived_tags = ";".join(derived_tags(lead))
    return lead


def score_leads(leads: list[Lead]) -> list[Lead]:
    scored = [score_lead(lead) for lead in leads]
    scored.sort(key=lambda item: (-item.opportunity_score, -item.lead_score, item.name.lower()))
    return scored
