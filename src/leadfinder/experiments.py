"""Local prospecting experiments. Evaluation is descriptive, not causal."""

from __future__ import annotations

from dataclasses import dataclass

from leadfinder.analytics import LeadFacts, Rate, historical_flags
from leadfinder.insights import (
    MIN_RECOMMENDATION_SAMPLE,
    evaluate_vs_baseline,
)
from leadfinder.models import Experiment


@dataclass
class ExperimentMetrics:
    experiment_id: int
    name: str
    status: str
    hypothesis: str
    target_metric: str
    target_label: str
    baseline: Rate
    observed: Rate
    sample: int
    difference_pp: float | None
    evaluation: str
    period_label: str

    def as_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "status": self.status,
            "hypothesis": self.hypothesis,
            "target_metric": self.target_metric,
            "target_label": self.target_label,
            "baseline": self.baseline.as_dict(),
            "observed": self.observed.as_dict(),
            "sample": self.sample,
            "difference_pp": self.difference_pp,
            "evaluation": self.evaluation,
            "period_label": self.period_label,
        }

    def to_ai_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "hypothesis": self.hypothesis,
            "target_metric": self.target_metric,
            "target_label": self.target_label,
            "baseline_rate": self.baseline.value,
            "baseline_n": self.baseline.denominator,
            "observed_rate": self.observed.value,
            "observed_n": self.observed.denominator,
            "difference_pp": self.difference_pp,
            "evaluation": self.evaluation,
            "period": self.period_label,
        }


def target_label(experiment: Experiment) -> str:
    parts: list[str] = []
    if experiment.business_preset:
        parts.append(experiment.business_preset.replace("_", " ").title())
    if experiment.location:
        parts.append(experiment.location)
    if experiment.digital_presence:
        from leadfinder.analytics import PRESENCE_LABELS

        parts.append(
            PRESENCE_LABELS.get(experiment.digital_presence, experiment.digital_presence)
        )
    if experiment.opportunity_level:
        parts.append(experiment.opportunity_level.replace("_", " ").title())
    return " + ".join(parts) if parts else "All matching leads"


def lead_matches(lead: LeadFacts, experiment: Experiment) -> bool:
    if experiment.business_preset and lead.business_preset != experiment.business_preset:
        return False
    if experiment.location and lead.location != experiment.location:
        return False
    if experiment.digital_presence and lead.website_status != experiment.digital_presence:
        return False
    if experiment.opportunity_level and lead.opportunity_level != experiment.opportunity_level:
        return False
    return True


def scoped_leads(
    leads: list[LeadFacts],
    experiment: Experiment,
    campaign_ids: frozenset[int],
) -> list[LeadFacts]:
    matched: list[LeadFacts] = []
    for lead in leads:
        if campaign_ids and not (lead.campaign_ids & campaign_ids):
            continue
        if lead_matches(lead, experiment):
            matched.append(lead)
    return matched


def observed_contact_to_interest(leads: list[LeadFacts]) -> Rate:
    contacted = interested = 0
    for lead in leads:
        once, interest, _won, _fallback = historical_flags(lead)
        contacted += int(once)
        interested += int(interest)
    value = None
    if contacted >= MIN_RECOMMENDATION_SAMPLE:
        value = round(100.0 * interested / contacted, 1)
    elif contacted > 0:
        value = round(100.0 * interested / contacted, 1)
    return Rate(numerator=interested, denominator=contacted, value=value)


def evaluate_experiment(
    experiment: Experiment,
    leads: list[LeadFacts],
    baseline: Rate,
    *,
    period_label: str,
    campaign_ids: frozenset[int] = frozenset(),
) -> ExperimentMetrics:
    scoped = scoped_leads(leads, experiment, campaign_ids)
    observed = observed_contact_to_interest(scoped)
    evaluation = evaluate_vs_baseline(observed, baseline)
    diff = None
    if observed.value is not None and baseline.value is not None:
        diff = round(observed.value - baseline.value, 1)
    return ExperimentMetrics(
        experiment_id=experiment.id,
        name=experiment.name,
        status=experiment.status,
        hypothesis=experiment.hypothesis,
        target_metric=experiment.target_metric or "contact_to_interest",
        target_label=target_label(experiment),
        baseline=baseline,
        observed=observed,
        sample=observed.denominator,
        difference_pp=diff,
        evaluation=evaluation,
        period_label=period_label,
    )
