from __future__ import annotations

import re

from leadfinder.ai.groq_provider import GroqProvider
from leadfinder.ai.models import SalesPrepRequest, SalesPrepResult
from leadfinder.ai.provider import AIProvider, groq_model
from leadfinder.models import ManagedLead

_SECRET_HINT = re.compile(r"(?:aiza|gsk_)[0-9a-za-z_-]{10,}", re.IGNORECASE)

PRESENCE_LABELS = {
    "no_website": "No website",
    "has_website": "Website",
    "social_only": "Social only",
    "link_aggregator": "Link aggregator",
    "unreachable": "Unreachable",
    "non_https": "HTTP only",
    "parked": "Parked",
    "weak_website": "Weak website",
    "unknown": "Unknown",
}


FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "phone",
        "api_key",
        "place_id",
        "website",
        "google_maps_url",
        "html",
        "raw",
    }
)


def build_sales_prep_request(item: ManagedLead, *, language: str) -> SalesPrepRequest:
    lead = item.lead
    return SalesPrepRequest(
        name=lead.name or item.label,
        business_type=lead.primary_type or lead.place_type or lead.business_preset,
        location=lead.source_location,
        region=lead.region,
        country=lead.country,
        rating=lead.rating,
        review_count=lead.user_rating_count,
        digital_presence=PRESENCE_LABELS.get(lead.website_status, lead.website_status),
        website_status=lead.website_status,
        qualification_signals=lead.lead_reason or lead.qualification_reason,
        opportunity_score=lead.opportunity_score,
        opportunity_level=lead.opportunity_level,
        contact_status=item.contact_status,
        notes=item.notes,
        tags=item.tags,
        operational=lead.operational,
        language=language,
    )


def assert_minimized(payload: dict[str, object]) -> None:
    lowered = {key.lower() for key in payload}
    overlap = lowered & FORBIDDEN_REQUEST_KEYS
    if overlap:
        raise ValueError(f"Sales prep payload includes forbidden keys: {sorted(overlap)}")
    blob = json_safe(payload)
    text = blob.lower()
    if "api_key" in text or "authorization" in text or _SECRET_HINT.search(blob):
        raise ValueError("Sales prep payload must not include secrets.")


def json_safe(payload: dict[str, object]) -> str:
    return " ".join(f"{key} {value}" for key, value in payload.items())


def generate_sales_prep(
    item: ManagedLead,
    *,
    language: str,
    model: str = "",
    provider: AIProvider | None = None,
) -> SalesPrepResult:
    request = build_sales_prep_request(item, language=language)
    assert_minimized(request.to_payload())
    engine = provider or GroqProvider(model=groq_model(model))
    return engine.generate_sales_prep(request)
