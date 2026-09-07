"""Deterministic campaign analytics. No SQL, no widgets, no AI."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from statistics import median

from leadfinder.labels import OPPORTUNITY_LABELS, PRESENCE_LABELS
from leadfinder.models import Activity
from leadfinder.workflow import (
    CONTACT_STATUSES,
    ActivityType,
    ContactStatus,
    conversion_rate,
    is_due_today,
    is_overdue,
    parse_utc,
    utc_now,
)

MIN_RATE_SAMPLE = 3
MIN_INSIGHT_SAMPLE = 5

CONTACTED_ONCE_STATUSES = frozenset(
    {
        ContactStatus.CONTACTED.value,
        ContactStatus.INTERESTED.value,
        ContactStatus.FOLLOW_UP.value,
        ContactStatus.WON.value,
    }
)
INTERESTED_ONCE_STATUSES = frozenset(
    {
        ContactStatus.INTERESTED.value,
        ContactStatus.FOLLOW_UP.value,
        ContactStatus.WON.value,
    }
)

_STATUS_FROM_LABEL = {status.replace("_", " "): status for status in CONTACT_STATUSES}


@dataclass(frozen=True)
class Period:
    start: datetime | None
    end: datetime | None
    label: str


@dataclass
class LeadFacts:
    place_id: str
    first_seen_at: str
    contact_status: str
    opportunity_level: str
    website_status: str
    business_preset: str
    location: str
    region: str
    country: str
    next_follow_up_at: str
    activities: tuple[Activity, ...] = ()
    campaign_ids: frozenset[int] = field(default_factory=frozenset)


@dataclass
class Rate:
    numerator: int
    denominator: int
    value: float | None

    def as_dict(self) -> dict[str, int | float | None]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
        }


@dataclass
class SnapshotMetrics:
    total_leads: int
    high_opportunity: int
    medium_opportunity: int
    low_opportunity: int
    new: int
    contacted: int
    interested: int
    follow_up: int
    won: int
    rejected: int
    do_not_contact: int
    due_followups: int
    overdue_followups: int


@dataclass
class HistoricalMetrics:
    total_leads: int
    contacted_once: int
    interested_once: int
    won_once: int
    fallback_status_only: int


@dataclass
class DurationStat:
    median_days: float | None
    n: int


@dataclass
class SegmentRow:
    key: str
    label: str
    leads: int
    contacted: int
    interested: int
    won: int
    contact_to_interest: float | None


@dataclass
class MethodRow:
    key: str
    label: str
    leads: int
    interested: int
    won: int
    contact_to_interest: float | None


@dataclass
class WeeklyRow:
    week_start: str
    leads: int
    contacted: int
    interested: int
    won: int


@dataclass
class AnalyticsReport:
    period_label: str
    campaign_id: int | None
    campaign_name: str
    generated_at: str
    snapshot: SnapshotMetrics
    historical: HistoricalMetrics
    contact_rate: Rate
    contact_to_interest: Rate
    contact_to_win: Rate
    interest_to_win: Rate
    follow_up_activities: int
    time_to_first_contact: DurationStat
    time_contact_to_interest: DurationStat
    time_interest_to_won: DurationStat
    by_business: list[SegmentRow]
    by_location: list[SegmentRow]
    by_presence: list[SegmentRow]
    by_opportunity: list[SegmentRow]
    by_method: list[MethodRow]
    weekly: list[WeeklyRow]
    ai_prep_saved: int
    ai_prep_interested: int
    ai_prep_won: int
    observations: list[str]
    campaign_notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "period_label": self.period_label,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "generated_at": self.generated_at,
            "snapshot": asdict(self.snapshot),
            "historical": asdict(self.historical),
            "contact_rate": self.contact_rate.as_dict(),
            "contact_to_interest": self.contact_to_interest.as_dict(),
            "contact_to_win": self.contact_to_win.as_dict(),
            "interest_to_win": self.interest_to_win.as_dict(),
            "follow_up_activities": self.follow_up_activities,
            "time_to_first_contact": asdict(self.time_to_first_contact),
            "time_contact_to_interest": asdict(self.time_contact_to_interest),
            "time_interest_to_won": asdict(self.time_interest_to_won),
            "by_business": [asdict(row) for row in self.by_business],
            "by_location": [asdict(row) for row in self.by_location],
            "by_presence": [asdict(row) for row in self.by_presence],
            "by_opportunity": [asdict(row) for row in self.by_opportunity],
            "by_method": [asdict(row) for row in self.by_method],
            "weekly": [asdict(row) for row in self.weekly],
            "ai_prep_saved": self.ai_prep_saved,
            "ai_prep_interested": self.ai_prep_interested,
            "ai_prep_won": self.ai_prep_won,
            "observations": list(self.observations),
            "campaign_notes": self.campaign_notes,
        }


def local_timezone() -> tzinfo:
    zone = datetime.now().astimezone().tzinfo
    if zone is None:
        return timezone.utc
    return zone


def period_last_days(days: int, *, now: datetime | None = None) -> Period:
    current = utc_now(now)
    return Period(start=current - timedelta(days=days), end=None, label=f"Last {days} days")


def period_all_time() -> Period:
    return Period(start=None, end=None, label="All time")


def period_custom(start: datetime, end: datetime) -> Period:
    return Period(
        start=utc_now(start),
        end=utc_now(end),
        label=f"{utc_now(start).date().isoformat()} – {utc_now(end).date().isoformat()}",
    )


def in_period(stamp: str, period: Period) -> bool:
    parsed = parse_utc(stamp)
    if parsed is None:
        return False
    if period.start is not None and parsed < period.start:
        return False
    if period.end is not None and parsed >= period.end:
        return False
    return True


def parse_status_change_target(activity: Activity) -> str | None:
    if activity.activity_type != ActivityType.STATUS_CHANGE.value:
        return None
    if activity.outcome in CONTACT_STATUSES:
        return activity.outcome
    note = activity.note.lower()
    if " to " not in note:
        return None
    tail = note.rsplit(" to ", 1)[-1].strip()
    if tail in CONTACT_STATUSES:
        return tail
    return _STATUS_FROM_LABEL.get(tail)


def _event_times(lead: LeadFacts) -> dict[str, datetime]:
    times: dict[str, datetime] = {}
    for activity in sorted(lead.activities, key=lambda item: (item.created_at, item.id)):
        stamp = parse_utc(activity.created_at)
        if stamp is None:
            continue
        if activity.activity_type == ActivityType.CONTACT_ATTEMPT.value:
            times.setdefault("contacted", stamp)
        target = parse_status_change_target(activity)
        if target in CONTACTED_ONCE_STATUSES:
            times.setdefault("contacted", stamp)
        if target in INTERESTED_ONCE_STATUSES:
            times.setdefault("interested", stamp)
        if target == ContactStatus.WON.value:
            times.setdefault("won", stamp)
    return times


def historical_flags(lead: LeadFacts) -> tuple[bool, bool, bool, bool]:
    """Return contacted_once, interested_once, won_once, used_status_fallback."""
    times = _event_times(lead)
    has_events = any(
        activity.activity_type
        in {ActivityType.STATUS_CHANGE.value, ActivityType.CONTACT_ATTEMPT.value}
        for activity in lead.activities
    )
    if has_events:
        return "contacted" in times, "interested" in times, "won" in times, False
    status = lead.contact_status
    if status in CONTACTED_ONCE_STATUSES:
        return (
            True,
            status in INTERESTED_ONCE_STATUSES,
            status == ContactStatus.WON.value,
            True,
        )
    return False, False, False, False


def _rate(numerator: int, denominator: int) -> Rate:
    value = conversion_rate(numerator, denominator)
    if denominator <= 0:
        value = None
    return Rate(numerator=numerator, denominator=denominator, value=value)


def _duration(samples: list[float]) -> DurationStat:
    if len(samples) < MIN_RATE_SAMPLE:
        return DurationStat(median_days=None, n=len(samples))
    return DurationStat(median_days=round(float(median(samples)), 1), n=len(samples))


def _days_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 86400.0


def local_week_start(stamp: str, tz: tzinfo) -> str | None:
    parsed = parse_utc(stamp)
    if parsed is None:
        return None
    local = parsed.astimezone(tz)
    monday = local.date() - timedelta(days=local.weekday())
    return monday.isoformat()


def _segment_rows(
    groups: dict[str, list[LeadFacts]],
    labels: dict[str, str] | None = None,
) -> list[SegmentRow]:
    rows: list[SegmentRow] = []
    for key, leads in groups.items():
        contacted = interested = won = 0
        for lead in leads:
            c, i, w, _fallback = historical_flags(lead)
            contacted += int(c)
            interested += int(i)
            won += int(w)
        label = (labels or {}).get(key, key.replace("_", " ").title() or "Unknown")
        rows.append(
            SegmentRow(
                key=key or "unknown",
                label=label,
                leads=len(leads),
                contacted=contacted,
                interested=interested,
                won=won,
                contact_to_interest=_rate(interested, contacted).value,
            )
        )
    rows.sort(key=lambda row: (-row.leads, row.label))
    return rows


def filter_leads(
    leads: list[LeadFacts],
    period: Period,
    *,
    campaign_id: int | None = None,
) -> list[LeadFacts]:
    selected: list[LeadFacts] = []
    for lead in leads:
        if campaign_id is not None and campaign_id not in lead.campaign_ids:
            continue
        if not in_period(lead.first_seen_at, period):
            continue
        selected.append(lead)
    return selected


def build_report(
    leads: list[LeadFacts],
    period: Period,
    *,
    campaign_id: int | None = None,
    campaign_name: str = "All campaigns",
    campaign_notes: str = "",
    now: datetime | None = None,
    tz: tzinfo | None = None,
    generated_at: str = "",
) -> AnalyticsReport:
    current = utc_now(now)
    zone = tz or local_timezone()
    scoped = filter_leads(leads, period, campaign_id=campaign_id)
    tallies = {status: 0 for status in CONTACT_STATUSES}
    high = medium = low = 0
    due = overdue = 0
    contacted_once = interested_once = won_once = fallback = 0
    to_contact: list[float] = []
    contact_to_interest: list[float] = []
    interest_to_won: list[float] = []
    follow_acts = 0
    by_business: dict[str, list[LeadFacts]] = defaultdict(list)
    by_location: dict[str, list[LeadFacts]] = defaultdict(list)
    by_presence: dict[str, list[LeadFacts]] = defaultdict(list)
    by_opportunity: dict[str, list[LeadFacts]] = defaultdict(list)
    method_leads: dict[str, set[str]] = defaultdict(set)
    weekly: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    prep_ids: set[str] = set()

    for lead in scoped:
        tallies[lead.contact_status] = tallies.get(lead.contact_status, 0) + 1
        if lead.opportunity_level == "high":
            high += 1
        elif lead.opportunity_level == "medium":
            medium += 1
        else:
            low += 1
        if is_overdue(lead.contact_status, lead.next_follow_up_at, now=current):
            overdue += 1
        elif is_due_today(lead.contact_status, lead.next_follow_up_at, now=current):
            due += 1
        contacted, interested, won, used_fallback = historical_flags(lead)
        contacted_once += int(contacted)
        interested_once += int(interested)
        won_once += int(won)
        fallback += int(used_fallback)
        times = _event_times(lead)
        seen = parse_utc(lead.first_seen_at)
        if seen and "contacted" in times:
            to_contact.append(_days_between(seen, times["contacted"]))
        if "contacted" in times and "interested" in times:
            contact_to_interest.append(_days_between(times["contacted"], times["interested"]))
        if "interested" in times and "won" in times:
            interest_to_won.append(_days_between(times["interested"], times["won"]))
        for activity in lead.activities:
            if activity.activity_type == ActivityType.FOLLOW_UP.value:
                follow_acts += 1
            if activity.activity_type == ActivityType.SALES_PREP_SAVED.value:
                prep_ids.add(lead.place_id)
            if activity.contact_method:
                method_leads[activity.contact_method].add(lead.place_id)
        by_business[lead.business_preset or "unknown"].append(lead)
        by_location[lead.location or "unknown"].append(lead)
        by_presence[lead.website_status or "unknown"].append(lead)
        by_opportunity[lead.opportunity_level or "unknown"].append(lead)
        week = local_week_start(lead.first_seen_at, zone)
        if week:
            weekly[week][0] += 1
        for index, key in ((1, "contacted"), (2, "interested"), (3, "won")):
            if key in times:
                event_week = local_week_start(times[key].isoformat(), zone)
                if event_week:
                    weekly[event_week][index] += 1
            elif key == "contacted" and contacted and week:
                weekly[week][1] += 1
            elif key == "interested" and interested and week:
                weekly[week][2] += 1
            elif key == "won" and won and week:
                weekly[week][3] += 1

    methods: list[MethodRow] = []
    facts_by_id = {lead.place_id: lead for lead in scoped}
    for method, ids in method_leads.items():
        method_interested = 0
        method_won = 0
        for place_id in ids:
            _c, is_int, is_won, _f = historical_flags(facts_by_id[place_id])
            method_interested += int(is_int)
            method_won += int(is_won)
        methods.append(
            MethodRow(
                key=method,
                label=method.replace("_", " ").title(),
                leads=len(ids),
                interested=method_interested,
                won=method_won,
                contact_to_interest=_rate(method_interested, len(ids)).value,
            )
        )
    methods.sort(key=lambda row: (-row.leads, row.label))

    prep_interested = prep_won = 0
    for place_id in prep_ids:
        _c, i, w, _f = historical_flags(facts_by_id[place_id])
        prep_interested += int(i)
        prep_won += int(w)

    snapshot = SnapshotMetrics(
        total_leads=len(scoped),
        high_opportunity=high,
        medium_opportunity=medium,
        low_opportunity=low,
        new=tallies.get(ContactStatus.NEW.value, 0),
        contacted=tallies.get(ContactStatus.CONTACTED.value, 0),
        interested=tallies.get(ContactStatus.INTERESTED.value, 0),
        follow_up=tallies.get(ContactStatus.FOLLOW_UP.value, 0),
        won=tallies.get(ContactStatus.WON.value, 0),
        rejected=tallies.get(ContactStatus.REJECTED.value, 0),
        do_not_contact=tallies.get(ContactStatus.DO_NOT_CONTACT.value, 0),
        due_followups=due,
        overdue_followups=overdue,
    )
    historical = HistoricalMetrics(
        total_leads=len(scoped),
        contacted_once=contacted_once,
        interested_once=interested_once,
        won_once=won_once,
        fallback_status_only=fallback,
    )
    presence_rows = _segment_rows(by_presence, PRESENCE_LABELS)
    business_rows = _segment_rows(
        by_business,
        {key: key.replace("_", " ").title() for key in by_business},
    )
    observations = _observations(business_rows, presence_rows)
    week_rows = [
        WeeklyRow(
            week_start=week,
            leads=vals[0],
            contacted=vals[1],
            interested=vals[2],
            won=vals[3],
        )
        for week, vals in sorted(weekly.items())
    ]
    return AnalyticsReport(
        period_label=period.label,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        generated_at=generated_at or current.isoformat(),
        snapshot=snapshot,
        historical=historical,
        contact_rate=_rate(contacted_once, len(scoped)),
        contact_to_interest=_rate(interested_once, contacted_once),
        contact_to_win=_rate(won_once, contacted_once),
        interest_to_win=_rate(won_once, interested_once),
        follow_up_activities=follow_acts,
        time_to_first_contact=_duration(to_contact),
        time_contact_to_interest=_duration(contact_to_interest),
        time_interest_to_won=_duration(interest_to_won),
        by_business=business_rows,
        by_location=_segment_rows(
            by_location,
            {key: key.title() if key != "unknown" else "Unknown" for key in by_location},
        ),
        by_presence=presence_rows,
        by_opportunity=_segment_rows(by_opportunity, OPPORTUNITY_LABELS),
        by_method=methods,
        weekly=week_rows,
        ai_prep_saved=len(prep_ids),
        ai_prep_interested=prep_interested,
        ai_prep_won=prep_won,
        observations=observations,
        campaign_notes=campaign_notes,
    )


def _observations(business: list[SegmentRow], presence: list[SegmentRow]) -> list[str]:
    notes: list[str] = []
    candidates = [row for row in business + presence if (row.contacted or 0) >= MIN_INSIGHT_SAMPLE]
    scored = [row for row in candidates if row.contact_to_interest is not None]
    if not scored:
        return notes
    best = max(scored, key=lambda row: (row.contact_to_interest or 0.0, row.contacted))
    notes.append(
        "In your recorded data, "
        f"{best.label} has the highest contact→interest rate among segments with at least "
        f"{MIN_INSIGHT_SAMPLE} contacted leads ({best.contact_to_interest}% · n={best.contacted} "
        "contacted). Correlation only — not a causal claim."
    )
    return notes


def format_rate(rate: Rate) -> str:
    if rate.denominator <= 0 or rate.value is None:
        return "Not enough data"
    return f"{rate.value}%"


def auto_campaign_name(preset: str, location: str, local_day: str) -> str:
    label = preset.replace("_", " ").title() or "Search"
    place = location.strip() or "Unknown"
    return f"{label} · {place} · {local_day}"


def compare_reports(left: AnalyticsReport, right: AnalyticsReport) -> list[tuple[str, str, str]]:
    return [
        ("Leads", str(left.historical.total_leads), str(right.historical.total_leads)),
        (
            "High opportunity",
            str(left.snapshot.high_opportunity),
            str(right.snapshot.high_opportunity),
        ),
        (
            "Contacted (once)",
            str(left.historical.contacted_once),
            str(right.historical.contacted_once),
        ),
        (
            "Interested (once)",
            str(left.historical.interested_once),
            str(right.historical.interested_once),
        ),
        ("Won (once)", str(left.historical.won_once), str(right.historical.won_once)),
        ("Contact rate", format_rate(left.contact_rate), format_rate(right.contact_rate)),
        (
            "Contact→Interest",
            format_rate(left.contact_to_interest),
            format_rate(right.contact_to_interest),
        ),
        ("Contact→Win", format_rate(left.contact_to_win), format_rate(right.contact_to_win)),
        ("Interest→Win", format_rate(left.interest_to_win), format_rate(right.interest_to_win)),
    ]


def coerce_timezone(name: str) -> tzinfo:
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return local_timezone()
