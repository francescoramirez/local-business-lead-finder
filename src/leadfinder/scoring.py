from __future__ import annotations

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
WEAK_WEB_STATUSES = {"social_only", "link_aggregator", "unreachable", "non_https"}


def score_lead(lead: Lead) -> Lead:
    annotate_flags(lead)
    score = 0
    reasons: list[str] = []

    status = (lead.business_status or "").upper()
    if status == CLOSED_PERMANENTLY:
        score -= PENALTY_CLOSED_PERMANENTLY
        reasons.append("closed permanently (-50)")
    elif status == CLOSED_TEMPORARILY:
        score -= PENALTY_CLOSED_TEMPORARILY
        reasons.append("closed temporarily (-20)")
    elif lead.operational:
        score += SCORE_OPERATIONAL
        reasons.append("operational (+15)")

    if not lead.has_website:
        score += SCORE_NO_WEBSITE
        reasons.append("no website listed (+40)")
    elif lead.website_status in WEAK_WEB_STATUSES:
        score += SCORE_WEAK_WEB_PRESENCE
        reasons.append(f"{lead.website_status.replace('_', ' ')} (+20)")

    if lead.contactable:
        score += SCORE_PHONE
        reasons.append("has phone (+10)")

    reviews = lead.user_rating_count or 0
    if reviews >= 10:
        score += SCORE_ACTIVE_REVIEWS
        reasons.append("review activity (+10)")
    elif reviews >= 1 or lead.rating is not None:
        score += SCORE_SOME_REVIEWS
        reasons.append("some public reviews (+5)")

    lead.lead_score = max(0, min(100, score))
    lead.lead_reason = "; ".join(reasons) if reasons else "no scoring signals"
    return lead


def score_leads(leads: list[Lead]) -> list[Lead]:
    scored = [score_lead(lead) for lead in leads]
    scored.sort(key=lambda item: (-item.lead_score, item.name.lower()))
    return scored
