from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from leadfinder.config import SearchConfig, get_api_key
from leadfinder.digital_presence import PresenceAnalyzer, analyze_leads
from leadfinder.errors import (
    ConfigError,
    LeadFinderError,
    MissingApiKeyError,
    PlacesAuthError,
    PlacesClientError,
    PlacesInvalidRequestError,
    PlacesRateLimitError,
    PlacesServerError,
)
from leadfinder.exporters import export_leads
from leadfinder.models import (
    Lead,
    ManagedLead,
    SearchPlan,
    SearchProgress,
    SearchReport,
    utc_now_iso,
)
from leadfinder.places_client import PlacesClient
from leadfinder.scoring import score_lead
from leadfinder.search import build_plan, run_search
from leadfinder.storage.local_leads import LocalLeadStore


def friendly_error(error: Exception) -> str:
    if isinstance(error, MissingApiKeyError):
        return (
            "No Places API key was found. Create a local .env file with "
            "GOOGLE_MAPS_API_KEY. The key is not entered in this window."
        )
    if isinstance(error, PlacesAuthError):
        return (
            "Google rejected the API credentials. Check that Places API (New) is "
            "enabled and that the key is restricted correctly."
        )
    if isinstance(error, PlacesRateLimitError):
        return "Google rate-limited the search (HTTP 429). Wait and try again with fewer requests."
    if isinstance(error, PlacesInvalidRequestError):
        return (
            "Google rejected the search configuration. "
            "Check location, country, and field profile."
        )
    if isinstance(error, PlacesServerError):
        return "Google Places is temporarily unavailable. Try again in a moment."
    if isinstance(error, PlacesClientError):
        return "Could not reach Google Places. Check the network connection and try again."
    if isinstance(error, ConfigError):
        return str(error)
    if isinstance(error, LeadFinderError):
        return str(error)
    return "Something went wrong while running the search."


def merge_local_state(leads: list[Lead], store: LocalLeadStore) -> list[ManagedLead]:
    known = store.get_many([lead.place_id for lead in leads if lead.place_id])
    merged: list[ManagedLead] = []
    for lead in leads:
        existing = known.get(lead.place_id)
        previously_seen = existing is not None
        state = store.mark_seen(lead.place_id) if lead.place_id else None
        merged.append(
            ManagedLead(
                lead=lead,
                contact_status=state.contact_status if state else "new",
                notes=state.notes if state else "",
                first_seen_at=state.first_seen_at if state else "",
                last_seen_at=state.last_seen_at if state else "",
                last_contacted_at=state.last_contacted_at if state else "",
                previously_seen=previously_seen,
            )
        )
    return merged


PRESENCE_FILTERS = {
    "no_website": frozenset({"no_website"}),
    "social_only": frozenset({"social_only"}),
    "link_aggregator": frozenset({"link_aggregator"}),
    "website": frozenset({"has_website", "weak_website", "parked", "non_https"}),
    "unreachable": frozenset({"unreachable"}),
}


def matches_filters(
    item: ManagedLead,
    *,
    text: str = "",
    min_score: int = 0,
    no_website_only: bool = False,
    has_phone: bool = False,
    operational_only: bool = False,
    contact_status: str = "",
    opportunity_level: str = "",
    presence: str = "",
) -> bool:
    lead = item.lead
    needle = text.strip().lower()
    if needle:
        blob = " ".join(
            [
                lead.name,
                lead.phone,
                lead.website,
                lead.address,
                lead.source_location,
                lead.website_status,
                lead.opportunity_level,
                item.notes,
                item.contact_status,
            ]
        ).lower()
        if needle not in blob:
            return False
    if lead.opportunity_score < min_score:
        return False
    if no_website_only and lead.has_website:
        return False
    if has_phone and not lead.contactable:
        return False
    if operational_only and not lead.operational:
        return False
    if contact_status and item.contact_status != contact_status:
        return False
    if opportunity_level and lead.opportunity_level != opportunity_level:
        return False
    if presence:
        allowed = PRESENCE_FILTERS.get(presence)
        if allowed is not None and lead.website_status not in allowed:
            return False
    return True


class LeadService:
    """GUI/CLI-facing facade over search, export, and local metadata."""

    def __init__(self, store: LocalLeadStore | None = None) -> None:
        self.store = store or LocalLeadStore()

    def dry_run(self, config: SearchConfig) -> SearchPlan:
        return build_plan(config)

    def require_api_key(self) -> str:
        return get_api_key()

    def search(
        self,
        config: SearchConfig,
        *,
        client: PlacesClient | None = None,
        on_progress: Callable[[SearchProgress], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> tuple[SearchReport, list[ManagedLead]]:
        api_client = client or PlacesClient(self.require_api_key())
        report = run_search(
            config,
            api_client,
            on_progress=on_progress,
            is_cancelled=is_cancelled,
            sleeper=sleeper,
        )
        managed = merge_local_state(report.leads, self.store)
        return report, managed

    def analyze_managed(
        self,
        items: list[ManagedLead],
        *,
        analyzer: PresenceAnalyzer | None = None,
        on_progress: Callable[[SearchProgress], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> list[ManagedLead]:
        engine = analyzer or PresenceAnalyzer()
        analyze_leads(
            [item.lead for item in items],
            analyzer=engine,
            is_cancelled=is_cancelled,
            on_progress=on_progress,
        )
        for item in items:
            score_lead(item.lead)
        return items

    def set_status(self, item: ManagedLead, status: str) -> ManagedLead:
        state = self.store.set_contact_status(item.lead.place_id, status)
        item.contact_status = state.contact_status
        item.last_contacted_at = state.last_contacted_at
        item.previously_seen = True
        return item

    def set_notes(self, item: ManagedLead, notes: str) -> ManagedLead:
        state = self.store.set_notes(item.lead.place_id, notes)
        item.notes = state.notes
        item.previously_seen = True
        return item

    def export(self, leads: list[Lead], *, fmt: str, output: Path | None = None) -> Path:
        stamp = utc_now_iso().replace(":", "").replace("-", "")[:15]
        paths = export_leads(
            leads,
            output=output,
            formats=(fmt,),
            stamp=stamp,
            force=bool(output),
        )
        return paths[0]
