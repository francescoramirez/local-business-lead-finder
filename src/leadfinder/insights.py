"""Deterministic outcome-driven insights. No ML, no individual leads."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from leadfinder.analytics import (
    MIN_INSIGHT_SAMPLE,
    OPPORTUNITY_LABELS,
    PRESENCE_LABELS,
    AnalyticsReport,
    LeadFacts,
    Rate,
    historical_flags,
)

MIN_RECOMMENDATION_SAMPLE = MIN_INSIGHT_SAMPLE
MIN_COMBINED_SAMPLE = 8
NEAR_BASELINE_PP = 3.0
UNKNOWN_KEYS = frozenset({"", "unknown"})


@dataclass
class SegmentInsight:
    dimension: str
    key: str
    label: str
    metric: str
    rate: float
    baseline: float
    uplift_pp: float
    n: int
    confidence: str
    contact_to_win: float | None = None
    interest_to_win: float | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class InsightsReport:
    period_label: str
    campaign_name: str
    baseline: Rate
    strongest: SegmentInsight | None
    weakest: SegmentInsight | None
    ranked: list[SegmentInsight] = field(default_factory=list)
    combinations: list[SegmentInsight] = field(default_factory=list)
    suggested_experiment: str = ""
    empty: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "period_label": self.period_label,
            "campaign_name": self.campaign_name,
            "baseline": self.baseline.as_dict(),
            "strongest": None if self.strongest is None else self.strongest.as_dict(),
            "weakest": None if self.weakest is None else self.weakest.as_dict(),
            "ranked": [row.as_dict() for row in self.ranked],
            "combinations": [row.as_dict() for row in self.combinations],
            "suggested_experiment": self.suggested_experiment,
            "empty": self.empty,
        }

    def to_ai_payload(self) -> dict[str, object]:
        """Aggregates only — no names, notes, phones, place IDs, or URLs."""
        return {
            "period": self.period_label,
            "campaign": self.campaign_name,
            "baseline_contact_to_interest": self.baseline.value,
            "baseline_n": self.baseline.denominator,
            "strongest": None if self.strongest is None else self.strongest.as_dict(),
            "weakest": None if self.weakest is None else self.weakest.as_dict(),
            "ranked_segments": [row.as_dict() for row in self.ranked[:8]],
            "combinations": [row.as_dict() for row in self.combinations[:6]],
            "suggested_experiment": self.suggested_experiment,
        }


def confidence_label(n: int) -> str:
    if n >= 20:
        return "High"
    if n >= 10:
        return "Medium"
    return "Low"


def format_uplift(pp: float) -> str:
    sign = "+" if pp > 0 else ""
    return f"{sign}{pp:.1f} pp"


def format_segment_line(row: SegmentInsight, *, prefix: str = "") -> str:
    return (
        f"{prefix}{row.label}: {row.rate}% "
        f"({format_uplift(row.uplift_pp)}, n={row.n}, {row.confidence})"
    )


def evaluate_vs_baseline(observed: Rate, baseline: Rate) -> str:
    if observed.denominator < MIN_RECOMMENDATION_SAMPLE or observed.value is None:
        return "Insufficient data"
    if baseline.denominator < MIN_RECOMMENDATION_SAMPLE or baseline.value is None:
        return "Insufficient data"
    diff = observed.value - baseline.value
    if abs(diff) < NEAR_BASELINE_PP:
        return "Near baseline"
    if diff > 0:
        return "Above baseline"
    return "Below baseline"


def _group_rate(leads: list[LeadFacts]) -> tuple[int, int, int, float | None, float | None]:
    contacted = interested = won = 0
    for lead in leads:
        c, i, w, _f = historical_flags(lead)
        contacted += int(c)
        interested += int(i)
        won += int(w)
    c2i = round(100.0 * interested / contacted, 1) if contacted else None
    c2w = round(100.0 * won / contacted, 1) if contacted else None
    return contacted, interested, won, c2i, c2w


def _insight(
    *,
    dimension: str,
    key: str,
    label: str,
    rate: float,
    n: int,
    baseline: float,
    contact_to_win: float | None,
    interest_to_win: float | None,
) -> SegmentInsight:
    return SegmentInsight(
        dimension=dimension,
        key=key,
        label=label,
        metric="contact_to_interest",
        rate=rate,
        baseline=baseline,
        uplift_pp=round(rate - baseline, 1),
        n=n,
        confidence=confidence_label(n),
        contact_to_win=contact_to_win,
        interest_to_win=interest_to_win,
    )


def _from_groups(
    groups: dict[str, list[LeadFacts]],
    labels: dict[str, str],
    dimension: str,
    baseline: float,
    min_n: int,
) -> list[SegmentInsight]:
    rows: list[SegmentInsight] = []
    for key, members in groups.items():
        if key.lower() in UNKNOWN_KEYS:
            continue
        contacted, _i, _w, c2i, c2w = _group_rate(members)
        if contacted < min_n or c2i is None:
            continue
        interested = sum(int(historical_flags(item)[1]) for item in members)
        won = sum(int(historical_flags(item)[2]) for item in members)
        i2w = round(100.0 * won / interested, 1) if interested else None
        label = labels.get(key, key.replace("_", " ").title())
        rows.append(
            _insight(
                dimension=dimension,
                key=key,
                label=label,
                rate=c2i,
                n=contacted,
                baseline=baseline,
                contact_to_win=c2w,
                interest_to_win=i2w,
            )
        )
    rows.sort(key=lambda row: (-row.uplift_pp, -row.n, row.label))
    return rows


def combo_labels_for(dimension: str, labels: dict[str, str]) -> dict[str, str]:
    prefix = f"{dimension}:"
    return {key.split(":", 1)[-1]: value for key, value in labels.items() if key.startswith(prefix)}


def build_insights(leads: list[LeadFacts], report: AnalyticsReport) -> InsightsReport:
    """Rank segments vs the report baseline. `leads` must already be period-scoped."""
    scoped = leads
    baseline = report.contact_to_interest
    base_rate = baseline.value
    if (
        base_rate is None
        or baseline.denominator < MIN_RECOMMENDATION_SAMPLE
        or not scoped
    ):
        return InsightsReport(
            period_label=report.period_label,
            campaign_name=report.campaign_name,
            baseline=baseline,
            strongest=None,
            weakest=None,
            suggested_experiment=(
                "Not enough history yet. Contact prospects and record outcomes "
                "before ranking segments."
            ),
            empty=True,
        )
    by_business: dict[str, list[LeadFacts]] = defaultdict(list)
    by_location: dict[str, list[LeadFacts]] = defaultdict(list)
    by_presence: dict[str, list[LeadFacts]] = defaultdict(list)
    by_opportunity: dict[str, list[LeadFacts]] = defaultdict(list)
    by_method: dict[str, list[LeadFacts]] = defaultdict(list)
    for lead in scoped:
        by_business[lead.business_preset or "unknown"].append(lead)
        by_location[lead.location or "unknown"].append(lead)
        by_presence[lead.website_status or "unknown"].append(lead)
        by_opportunity[lead.opportunity_level or "unknown"].append(lead)
        methods = {
            activity.contact_method
            for activity in lead.activities
            if activity.contact_method
        }
        for method in methods:
            by_method[method].append(lead)

    ranked: list[SegmentInsight] = []
    ranked.extend(
        _from_groups(
            by_business,
            {key: key.replace("_", " ").title() for key in by_business},
            "business",
            base_rate,
            MIN_RECOMMENDATION_SAMPLE,
        )
    )
    ranked.extend(
        _from_groups(
            by_location,
            {key: key for key in by_location},
            "location",
            base_rate,
            MIN_RECOMMENDATION_SAMPLE,
        )
    )
    ranked.extend(
        _from_groups(by_presence, PRESENCE_LABELS, "presence", base_rate, MIN_RECOMMENDATION_SAMPLE)
    )
    ranked.extend(
        _from_groups(
            by_opportunity,
            OPPORTUNITY_LABELS,
            "opportunity",
            base_rate,
            MIN_RECOMMENDATION_SAMPLE,
        )
    )
    ranked.extend(
        _from_groups(
            by_method,
            {key: key.replace("_", " ").title() for key in by_method},
            "contact_method",
            base_rate,
            MIN_RECOMMENDATION_SAMPLE,
        )
    )
    ranked.sort(key=lambda row: (-row.uplift_pp, -row.n, row.label))

    combos: dict[str, list[LeadFacts]] = defaultdict(list)
    combo_labels: dict[str, str] = {}
    for lead in scoped:
        pairs = (
            (
                "business+presence",
                f"{lead.business_preset}|{lead.website_status}",
                f"{lead.business_preset.replace('_', ' ').title()} + "
                f"{PRESENCE_LABELS.get(lead.website_status, lead.website_status)}",
                lead.business_preset,
                lead.website_status,
            ),
            (
                "presence+opportunity",
                f"{lead.website_status}|{lead.opportunity_level}",
                f"{PRESENCE_LABELS.get(lead.website_status, lead.website_status)} + "
                f"{OPPORTUNITY_LABELS.get(lead.opportunity_level, lead.opportunity_level)}",
                lead.website_status,
                lead.opportunity_level,
            ),
        )
        for dimension, key, label, left, right in pairs:
            if left.lower() in UNKNOWN_KEYS or right.lower() in UNKNOWN_KEYS:
                continue
            combos[f"{dimension}:{key}"].append(lead)
            combo_labels[f"{dimension}:{key}"] = label
    combinations: list[SegmentInsight] = []
    grouped: dict[str, dict[str, list[LeadFacts]]] = defaultdict(dict)
    for full_key, members in combos.items():
        dimension, key = full_key.split(":", 1)
        grouped[dimension][key] = members
    for dimension, mapping in grouped.items():
        combinations.extend(
            _from_groups(
                mapping,
                combo_labels_for(dimension, combo_labels),
                dimension,
                base_rate,
                MIN_COMBINED_SAMPLE,
            )
        )
    combinations.sort(key=lambda row: (-row.uplift_pp, -row.n, row.label))

    strongest = ranked[0] if ranked else None
    weakest = min(ranked, key=lambda row: (row.uplift_pp, -row.n)) if ranked else None
    if strongest is not None:
        experiment = (
            f"Run a focused campaign on {strongest.label} and compare contact->interest "
            f"to the {report.period_label} baseline of {base_rate}% (n={baseline.denominator}). "
            "Treat the result as correlation, not a causal claim."
        )
    else:
        experiment = "Not enough qualifying segments to suggest a next experiment."
    return InsightsReport(
        period_label=report.period_label,
        campaign_name=report.campaign_name,
        baseline=baseline,
        strongest=strongest,
        weakest=weakest,
        ranked=ranked,
        combinations=combinations[:12],
        suggested_experiment=experiment,
        empty=False,
    )
