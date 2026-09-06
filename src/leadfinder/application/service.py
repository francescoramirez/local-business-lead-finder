from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from leadfinder.ai.models import SalesPrepResult
from leadfinder.ai.provider import AIProvider
from leadfinder.ai.service import generate_sales_prep
from leadfinder.config import SearchConfig, get_api_key
from leadfinder.digital_presence import PresenceAnalyzer, analyze_leads
from leadfinder.errors import (
    AIAuthError,
    AINetworkError,
    AINotConfiguredError,
    AIRateLimitError,
    AIRequestError,
    AIResponseValidationError,
    AITimeoutError,
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
    Activity,
    Lead,
    LocalLeadState,
    ManagedLead,
    SearchPlan,
    SearchProgress,
    SearchReport,
    SearchRun,
    utc_now_iso,
)
from leadfinder.places_client import PlacesClient
from leadfinder.scoring import score_lead
from leadfinder.search import build_plan, run_search
from leadfinder.storage.local_leads import LocalLeadStore
from leadfinder.workflow import (
    PipelineCounts,
    contacted_to_interested_rate,
    interested_to_won_rate,
    matches_follow_up_view,
    parse_tags,
    pipeline_counts,
    shift_iso,
)


def friendly_error(error: Exception) -> str:
    if isinstance(error, AINotConfiguredError):
        return str(error)
    if isinstance(error, AIAuthError):
        return "AI API key invalid."
    if isinstance(error, AIRateLimitError):
        return "AI provider rate limit."
    if isinstance(error, AITimeoutError):
        return "AI provider timed out."
    if isinstance(error, AIResponseValidationError):
        return "AI returned an invalid structured response."
    if isinstance(error, AINetworkError):
        return "Could not reach AI provider."
    if isinstance(error, AIRequestError):
        return str(error)
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


def apply_state(item: ManagedLead, state: LocalLeadState) -> ManagedLead:
    item.contact_status = state.contact_status
    item.notes = state.notes
    item.first_seen_at = state.first_seen_at
    item.last_seen_at = state.last_seen_at
    item.last_contacted_at = state.last_contacted_at
    item.next_follow_up_at = state.next_follow_up_at
    item.last_activity_at = state.last_activity_at
    item.tags = state.tags
    item.label = state.label
    item.previously_seen = True
    return item


def merge_local_state(leads: list[Lead], store: LocalLeadStore) -> list[ManagedLead]:
    known = store.get_many([lead.place_id for lead in leads if lead.place_id])
    merged: list[ManagedLead] = []
    for lead in leads:
        existing = known.get(lead.place_id)
        previously_seen = existing is not None
        state = (
            store.mark_seen(
                lead.place_id,
                label=lead.name,
                opportunity_level=lead.opportunity_level,
                opportunity_score=lead.opportunity_score,
                has_phone=lead.contactable,
            )
            if lead.place_id
            else None
        )
        item = ManagedLead(
            lead=lead,
            previously_seen=previously_seen,
        )
        if state:
            apply_state(item, state)
            item.previously_seen = previously_seen
        merged.append(item)
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
    follow_up_view: str = "",
    tag: str = "",
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
                item.tags,
                item.label,
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
    if tag:
        if tag.strip().lower() not in parse_tags(item.tags):
            return False
    if follow_up_view and not matches_follow_up_view(
        item.contact_status, item.next_follow_up_at, follow_up_view
    ):
        return False
    return True


class LeadService:
    """GUI/CLI-facing facade over search, export, and local metadata."""

    def __init__(
        self,
        store: LocalLeadStore | None = None,
        *,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self.store = store or LocalLeadStore()
        self.ai_provider = ai_provider

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
        location = config.locations[0] if config.locations else ""
        self.store.record_search(
            business_preset=config.business,
            location=location,
            region=config.region,
            country=config.country,
            lead_count=len(managed),
            high_opportunity_count=sum(
                1 for item in managed if item.lead.opportunity_level == "high"
            ),
        )
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

    def prepare_sales(
        self,
        item: ManagedLead,
        *,
        language: str,
        model: str = "",
    ) -> SalesPrepResult:
        return generate_sales_prep(
            item,
            language=language,
            model=model,
            provider=self.ai_provider,
        )

    def save_sales_prep(self, item: ManagedLead, result: SalesPrepResult) -> ManagedLead:
        block = result.as_notes_block()
        notes = item.notes.strip()
        merged = f"{notes}\n\n{block}".strip() if notes else block
        updated = self.set_notes(item, merged)
        updated, _activity = self.add_activity(
            updated,
            "sales_prep_saved",
            note="Saved AI sales prep to notes",
        )
        return updated

    def set_status(self, item: ManagedLead, status: str) -> ManagedLead:
        state = self.store.set_contact_status(item.lead.place_id, status)
        return apply_state(item, state)

    def set_notes(self, item: ManagedLead, notes: str) -> ManagedLead:
        state = self.store.set_notes(item.lead.place_id, notes)
        return apply_state(item, state)

    def set_tags(self, item: ManagedLead, tags: str) -> ManagedLead:
        state = self.store.set_tags(item.lead.place_id, tags)
        return apply_state(item, state)

    def set_follow_up(self, item: ManagedLead, when: str) -> ManagedLead:
        state = self.store.set_follow_up(item.lead.place_id, when)
        return apply_state(item, state)

    def schedule_in_days(self, item: ManagedLead, days: int) -> ManagedLead:
        return self.set_follow_up(item, shift_iso(days))

    def add_activity(
        self,
        item: ManagedLead,
        activity_type: str,
        *,
        note: str = "",
        contact_method: str = "",
        outcome: str = "",
    ) -> tuple[ManagedLead, Activity]:
        activity = self.store.add_activity(
            item.lead.place_id,
            activity_type,
            note=note,
            contact_method=contact_method,
            outcome=outcome,
        )
        state = self.store.get(item.lead.place_id)
        if state:
            apply_state(item, state)
        return item, activity

    def activities(self, place_id: str) -> list[Activity]:
        return self.store.list_activities(place_id)

    def prospects(self) -> list[LocalLeadState]:
        return self.store.list_all()

    def search_history(self) -> list[SearchRun]:
        return self.store.list_searches()

    def dashboard(self) -> PipelineCounts:
        return pipeline_counts(self.store.pipeline_rows())

    def conversion_summary(self) -> dict[str, float | None]:
        counts = self.dashboard()
        return {
            "contacted_to_interested": contacted_to_interested_rate(counts),
            "interested_to_won": interested_to_won_rate(counts),
        }

    def backup(self, destination: Path) -> Path:
        return self.store.backup(destination)

    def export_pipeline(self, items: list[ManagedLead], output: Path) -> Path:
        from leadfinder.exporters import write_pipeline_csv

        return write_pipeline_csv(items, output, force=True)

    def export_activities(self, place_ids: list[str], output: Path) -> Path:
        from leadfinder.exporters import write_activities_json

        payload = []
        for place_id in place_ids:
            for activity in self.store.list_activities(place_id):
                payload.append(
                    {
                        "id": activity.id,
                        "place_id": activity.place_id,
                        "activity_type": activity.activity_type,
                        "created_at": activity.created_at,
                        "note": activity.note,
                        "contact_method": activity.contact_method,
                        "outcome": activity.outcome,
                    }
                )
        return write_activities_json(payload, output, force=True)

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
