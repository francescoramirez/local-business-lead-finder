from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from leadfinder.ai.models import InsightsExplanation, SalesPrepResult
from leadfinder.ai.provider import AIProvider
from leadfinder.ai.service import generate_insights_explanation, generate_sales_prep
from leadfinder.analytics import (
    AnalyticsReport,
    Period,
    auto_campaign_name,
    build_report,
    filter_leads,
    local_timezone,
    period_all_time,
    period_custom,
    period_last_days,
)
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
    DatabaseError,
    LeadFinderError,
    MissingApiKeyError,
    PlacesAuthError,
    PlacesClientError,
    PlacesInvalidRequestError,
    PlacesRateLimitError,
    PlacesServerError,
    RestoreError,
    WorkspaceError,
)
from leadfinder.exporters import export_leads
from leadfinder.models import (
    Activity,
    Campaign,
    Experiment,
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
    if isinstance(error, DatabaseError):
        return str(error)
    if isinstance(error, RestoreError):
        return str(error)
    if isinstance(error, WorkspaceError):
        return str(error)
    if isinstance(error, ConfigError):
        return str(error)
    if isinstance(error, LeadFinderError):
        return str(error)
    return "Something went wrong. Details were written to the local log."


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
    item.manual_priority = state.manual_priority
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
                business_preset=lead.business_preset,
                source_location=lead.source_location,
                region=lead.region,
                country=lead.country,
                website_status=lead.website_status,
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
    manual_priority: str = "",
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
    if manual_priority and item.manual_priority != manual_priority:
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
        campaign_id: int | None = None,
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
        campaign = self.resolve_campaign(
            campaign_id,
            business_preset=config.business,
            location=location,
            region=config.region,
            country=config.country,
        )
        self.store.attach_leads(campaign.id, [item.lead.place_id for item in managed])
        self.store.record_search(
            business_preset=config.business,
            location=location,
            region=config.region,
            country=config.country,
            lead_count=len(managed),
            high_opportunity_count=sum(
                1 for item in managed if item.lead.opportunity_level == "high"
            ),
            campaign_id=campaign.id,
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
            if item.lead.place_id:
                self.store.mark_seen(
                    item.lead.place_id,
                    label=item.lead.name,
                    opportunity_level=item.lead.opportunity_level,
                    opportunity_score=item.lead.opportunity_score,
                    has_phone=item.lead.contactable,
                    business_preset=item.lead.business_preset,
                    source_location=item.lead.source_location,
                    region=item.lead.region,
                    country=item.lead.country,
                    website_status=item.lead.website_status,
                )
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

    def set_priority(self, item: ManagedLead, priority: str) -> ManagedLead:
        state = self.store.set_manual_priority(item.lead.place_id, priority)
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

    def resolve_campaign(
        self,
        campaign_id: int | None,
        *,
        business_preset: str,
        location: str,
        region: str,
        country: str,
        now: datetime | None = None,
    ) -> Campaign:
        if campaign_id:
            found = self.store.get_campaign(campaign_id)
            if found is not None:
                return found
        stamp = now or datetime.now().astimezone()
        local_day = stamp.date().isoformat()
        existing = self.store.find_auto_campaign(
            business_preset=business_preset,
            location=location,
            region=region,
            country=country,
            local_day=local_day,
        )
        if existing is not None:
            return existing
        return self.store.create_campaign(
            name=auto_campaign_name(business_preset, location, local_day),
            business_preset=business_preset,
            location=location,
            region=region,
            country=country,
            auto_created=True,
            local_day=local_day,
        )

    def create_campaign(
        self,
        *,
        name: str,
        business_preset: str = "",
        location: str = "",
        region: str = "",
        country: str = "",
        notes: str = "",
    ) -> Campaign:
        return self.store.create_campaign(
            name=name,
            business_preset=business_preset,
            location=location,
            region=region,
            country=country,
            notes=notes,
            auto_created=False,
        )

    def campaigns(self) -> list[Campaign]:
        return self.store.list_campaigns()

    def analytics_period(
        self,
        *,
        days: int | None = 30,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Period:
        if start is not None and end is not None:
            return period_custom(start, end)
        if days is None or days <= 0:
            return period_all_time()
        return period_last_days(days)

    def analytics_report(
        self,
        period: Period | None = None,
        *,
        campaign_id: int | None = None,
        days: int | None = 30,
        now: datetime | None = None,
    ) -> AnalyticsReport:
        window = period or self.analytics_period(days=days)
        campaign_name = "All campaigns"
        notes = ""
        if campaign_id:
            campaign = self.store.get_campaign(campaign_id)
            if campaign is not None:
                campaign_name = campaign.name
                notes = campaign.notes
        return build_report(
            self.store.load_lead_facts(),
            window,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            campaign_notes=notes,
            now=now,
            tz=local_timezone(),
        )

    def export_analytics(self, report: AnalyticsReport, output: Path) -> Path:
        from leadfinder.exporters import (
            write_analytics_csv,
            write_analytics_json,
            write_analytics_markdown,
        )

        suffix = output.suffix.lower()
        if suffix == ".json":
            return write_analytics_json(report, output, force=True)
        if suffix == ".md":
            return write_analytics_markdown(report, output, force=True)
        return write_analytics_csv(report, output, force=True)

    def insights_report(
        self,
        period: Period | None = None,
        *,
        campaign_id: int | None = None,
        days: int | None = 30,
        now: datetime | None = None,
    ):
        from leadfinder.insights import InsightsReport, build_insights

        window = period or self.analytics_period(days=days)
        report = self.analytics_report(
            window, campaign_id=campaign_id, days=days, now=now
        )
        scoped = filter_leads(
            self.store.load_lead_facts(),
            window,
            campaign_id=campaign_id,
        )
        insights: InsightsReport = build_insights(scoped, report)
        return insights

    def export_insights(self, report, output: Path) -> Path:
        from leadfinder.exporters import write_insights_json, write_insights_markdown

        suffix = output.suffix.lower()
        if suffix == ".md":
            return write_insights_markdown(report, output, force=True)
        return write_insights_json(report, output, force=True)

    def explain_insights(
        self,
        report,
        *,
        language: str = "Spanish",
        model: str = "",
        experiment: bool = False,
    ) -> InsightsExplanation:
        payload = report.to_ai_payload()
        return generate_insights_explanation(
            payload,
            language=language,
            model=model,
            provider=self.ai_provider,
            experiment=experiment,
        )

    def create_experiment(
        self,
        *,
        name: str,
        hypothesis: str = "",
        business_preset: str = "",
        location: str = "",
        digital_presence: str = "",
        opportunity_level: str = "",
        notes: str = "",
        campaign_ids: list[int] | None = None,
    ) -> Experiment:
        experiment = self.store.create_experiment(
            name=name,
            hypothesis=hypothesis,
            business_preset=business_preset,
            location=location,
            digital_presence=digital_presence,
            opportunity_level=opportunity_level,
            notes=notes,
            status="draft",
        )
        if campaign_ids:
            self.store.attach_campaigns(experiment.id, campaign_ids)
            found = self.store.get_experiment(experiment.id)
            return found if found is not None else experiment
        return experiment

    def experiments(self) -> list[Experiment]:
        return self.store.list_experiments()

    def get_experiment(self, experiment_id: int) -> Experiment | None:
        return self.store.get_experiment(experiment_id)

    def update_experiment(self, experiment_id: int, **fields: str) -> Experiment:
        return self.store.update_experiment(experiment_id, **fields)

    def experiment_metrics(
        self,
        experiment: Experiment,
        *,
        days: int | None = 0,
        now: datetime | None = None,
    ):
        from leadfinder.experiments import evaluate_experiment

        window = self.analytics_period(days=days)
        report = self.analytics_report(window, now=now)
        campaign_ids = frozenset(experiment.campaign_ids)
        scoped = filter_leads(self.store.load_lead_facts(), window)
        return evaluate_experiment(
            experiment,
            scoped,
            report.contact_to_interest,
            period_label=report.period_label,
            campaign_ids=campaign_ids,
        )

    def restore(self, source: Path) -> Path:
        return self.store.restore(source)

    def export_workspace(
        self, destination: Path, *, settings: dict[str, object] | None = None
    ) -> Path:
        from leadfinder.workspace import export_workspace

        return export_workspace(self.store, destination, settings=settings)

    def import_workspace(self, source: Path) -> dict[str, int]:
        from leadfinder.workspace import import_workspace

        return import_workspace(self.store, source)

    def doctor(self):
        from leadfinder.doctor import run_doctor

        return run_doctor(self.store.path)

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
