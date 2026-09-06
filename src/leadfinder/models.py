from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Lead:
    place_id: str
    name: str
    phone: str
    website: str
    website_status: str
    address: str
    business_status: str
    types: str
    primary_type: str
    google_maps_url: str
    rating: float | None
    user_rating_count: int | None
    lead_score: int
    lead_reason: str
    has_website: bool
    contactable: bool
    operational: bool
    source_query: str
    source_location: str
    search_term: str
    business_preset: str
    place_type: str
    country: str
    region: str
    fetched_at: str
    data_source: str = "Google Maps"

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["rating"] = "" if self.rating is None else self.rating
        row["user_rating_count"] = "" if self.user_rating_count is None else self.user_rating_count
        row["has_website"] = "yes" if self.has_website else "no"
        row["contactable"] = "yes" if self.contactable else "no"
        row["operational"] = "yes" if self.operational else "no"
        return row


EXPORT_COLUMNS: tuple[str, ...] = (
    "place_id",
    "name",
    "phone",
    "website",
    "website_status",
    "address",
    "business_status",
    "types",
    "primary_type",
    "google_maps_url",
    "rating",
    "user_rating_count",
    "lead_score",
    "lead_reason",
    "has_website",
    "contactable",
    "operational",
    "source_query",
    "source_location",
    "search_term",
    "business_preset",
    "place_type",
    "country",
    "region",
    "fetched_at",
    "data_source",
)


@dataclass
class SearchPlan:
    business: str
    included_type: str
    search_terms: list[str]
    locations: list[str]
    country: str
    region: str
    coverage: str
    field_profile: str
    field_mask: str
    billing_tier: str
    page_size: int
    pages: int
    max_queries: int
    max_api_requests: int
    language_code: str
    only_no_website: bool
    include_closed: bool
    analyze_websites: bool


@dataclass
class SearchReport:
    leads: list[Lead]
    queries_executed: int
    api_requests: int
    cache_hits: int
    places_found: int
    duplicates_discarded: int
    operational: int
    no_website: int
    contactable: int
    output_paths: list[str] = field(default_factory=list)
