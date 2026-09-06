from __future__ import annotations

from typing import Any

from leadfinder.models import Lead, utc_now_iso


def _display_name(place: dict[str, Any]) -> str:
    name = place.get("displayName")
    if isinstance(name, dict):
        return str(name.get("text") or "").strip()
    return str(name or "").strip()


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def place_to_lead(
    place: dict[str, Any],
    *,
    source_query: str,
    location: str,
    search_term: str,
    business_preset: str,
    place_type: str,
    country: str,
    region: str,
    fetched_at: str | None = None,
) -> Lead:
    website = str(place.get("websiteUri") or "").strip()
    phone = str(
        place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber") or ""
    ).strip()
    types = place.get("types") or []
    types_text = ";".join(str(item) for item in types if item)
    return Lead(
        place_id=str(place.get("id") or "").strip(),
        name=_display_name(place),
        phone=phone,
        website=website,
        website_status="has_website" if website else "no_website",
        address=str(place.get("formattedAddress") or "").strip(),
        business_status=str(place.get("businessStatus") or "").strip(),
        types=types_text,
        primary_type=str(place.get("primaryType") or "").strip(),
        google_maps_url=str(place.get("googleMapsUri") or "").strip(),
        rating=_as_float(place.get("rating")),
        user_rating_count=_as_int(place.get("userRatingCount")),
        lead_score=0,
        lead_reason="",
        has_website=bool(website),
        contactable=bool(phone),
        operational=False,
        source_query=source_query,
        source_location=location,
        search_term=search_term,
        business_preset=business_preset,
        place_type=place_type,
        country=country,
        region=region,
        fetched_at=fetched_at or utc_now_iso(),
    )
