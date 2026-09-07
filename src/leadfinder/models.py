from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from leadfinder.workflow import CONTACT_STATUS_LABELS as CONTACT_STATUS_LABELS
from leadfinder.workflow import CONTACT_STATUSES as CONTACT_STATUSES


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
    presence_type: str = "unknown"
    website_health: str = "unknown"
    https: str = "unknown"
    reachable: str = "unknown"
    final_url: str = ""
    presence_title: str = ""
    presence_signals: str = ""
    social_platform: str = ""
    digital_opportunity_score: int = 0
    opportunity_score: int = 0
    opportunity_level: str = "low"
    qualification_reason: str = ""
    derived_tags: str = ""

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["rating"] = "" if self.rating is None else self.rating
        row["user_rating_count"] = "" if self.user_rating_count is None else self.user_rating_count
        row["has_website"] = "yes" if self.has_website else "no"
        row["contactable"] = "yes" if self.contactable else "no"
        row["operational"] = "yes" if self.operational else "no"
        return {key: row[key] for key in EXPORT_COLUMNS}


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
    "presence_type",
    "website_health",
    "https",
    "reachable",
    "final_url",
    "presence_signals",
    "social_platform",
    "digital_opportunity_score",
    "opportunity_score",
    "opportunity_level",
    "qualification_reason",
    "derived_tags",
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
    cancelled: bool = False


@dataclass
class SearchProgress:
    message: str
    location: str = ""
    query: str = ""
    api_requests: int = 0
    places_found: int = 0
    leads_count: int = 0
    queries_executed: int = 0
    analyzed: int = 0
    analyze_total: int = 0


@dataclass
class LocalLeadState:
    place_id: str
    contact_status: str = "new"
    notes: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_contacted_at: str = ""
    tags: str = ""
    next_follow_up_at: str = ""
    last_activity_at: str = ""
    label: str = ""
    opportunity_level: str = ""
    opportunity_score: int = 0
    has_phone: bool = False
    business_preset: str = ""
    source_location: str = ""
    region: str = ""
    country: str = ""
    website_status: str = ""
    campaign_id: int = 0


@dataclass
class Activity:
    id: int
    place_id: str
    activity_type: str
    created_at: str
    note: str = ""
    contact_method: str = ""
    outcome: str = ""


@dataclass
class SearchRun:
    id: int
    created_at: str
    business_preset: str
    location: str
    region: str
    country: str
    lead_count: int
    high_opportunity_count: int
    campaign_id: int = 0


@dataclass
class Campaign:
    id: int
    name: str
    created_at: str
    notes: str = ""
    business_preset: str = ""
    location: str = ""
    region: str = ""
    country: str = ""
    auto_created: bool = False
    local_day: str = ""


EXPERIMENT_STATUSES = ("draft", "active", "completed", "archived")


@dataclass
class Experiment:
    id: int
    name: str
    created_at: str
    status: str = "draft"
    hypothesis: str = ""
    business_preset: str = ""
    location: str = ""
    digital_presence: str = ""
    opportunity_level: str = ""
    target_metric: str = "contact_to_interest"
    notes: str = ""
    observations: str = ""
    conclusion: str = ""
    campaign_ids: tuple[int, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ManagedLead:
    lead: Lead
    contact_status: str = "new"
    notes: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_contacted_at: str = ""
    previously_seen: bool = False
    next_follow_up_at: str = ""
    last_activity_at: str = ""
    tags: str = ""
    label: str = ""
