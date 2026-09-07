from __future__ import annotations

from decimal import Decimal

from leadfinder.costs.estimator import cost_per, estimate_requests, estimate_sku
from leadfinder.costs.models import CampaignCostSummary, CostEstimate
from leadfinder.costs.pricing import CATALOG_VERSION, CURRENCY
from leadfinder.errors import ConfigError
from leadfinder.fields import billing_sku_for_profile
from leadfinder.models import SearchRun

# Never subtract monthly free usage. Sum list-price estimates per completed page request.


def estimate_from_run(run: SearchRun) -> CostEstimate:
    if run.request_count <= 0:
        return CostEstimate(
            status="unknown",
            request_count=run.request_count,
            field_profile=run.field_profile,
            currency=run.currency or CURRENCY,
            amount=None,
            pricing_version=run.pricing_version,
            detail="Older search runs did not store cost metadata.",
            billing_sku=run.billing_sku,
        )
    sku = (run.billing_sku or "").strip()
    if not sku and run.field_profile:
        try:
            sku = billing_sku_for_profile(run.field_profile)
        except ConfigError:
            sku = ""
    if sku:
        return estimate_sku(
            run.request_count, sku, field_profile=run.field_profile
        )
    if not run.field_profile:
        return CostEstimate(
            status="unknown",
            request_count=run.request_count,
            field_profile=run.field_profile,
            currency=run.currency or CURRENCY,
            amount=None,
            pricing_version=run.pricing_version,
            detail="Older search runs did not store a billing SKU or field profile.",
        )
    return estimate_requests(run.request_count, run.field_profile)


def summarize_campaign_costs(
    runs: list[SearchRun],
    *,
    campaign_id: int,
    discovered_leads: int,
    high_opportunity_leads: int,
    interested_once: int,
    won_once: int,
) -> CampaignCostSummary:
    scoped = [run for run in runs if not campaign_id or run.campaign_id == campaign_id]
    requests = 0
    spend = Decimal("0.00")
    known = 0
    unknown = 0
    for run in scoped:
        estimate = estimate_from_run(run)
        requests += estimate.request_count
        if estimate.known and estimate.amount is not None:
            spend += estimate.amount
            known += 1
        else:
            unknown += 1
    if not scoped:
        status = "unknown"
        amount: Decimal | None = None
    elif unknown and known:
        status = "partial"
        amount = spend
    elif unknown:
        status = "unknown"
        amount = None
    else:
        status = "known"
        amount = spend
    return CampaignCostSummary(
        campaign_id=campaign_id,
        request_count=requests,
        known_spend=amount,
        unknown_runs=unknown,
        discovered_leads=discovered_leads,
        high_opportunity_leads=high_opportunity_leads,
        interested_once=interested_once,
        won_once=won_once,
        currency=CURRENCY,
        pricing_version=CATALOG_VERSION,
        status=status,
    )


def format_campaign_costs(summary: CampaignCostSummary) -> str:
    from leadfinder.costs.models import format_estimate

    estimate = CostEstimate(
        status=summary.status,
        request_count=summary.request_count,
        field_profile="",
        currency=summary.currency,
        amount=summary.known_spend,
        pricing_version=summary.pricing_version,
    )
    lines = [
        "Campaign estimated list cost (not an invoice)",
        f"Completed page requests: {summary.request_count}",
        format_estimate(estimate),
    ]
    if summary.unknown_runs:
        lines.append(f"Search runs without cost data: {summary.unknown_runs}")
    per_lead = cost_per(summary.known_spend, summary.discovered_leads)
    per_high = cost_per(summary.known_spend, summary.high_opportunity_leads)
    per_interest = cost_per(summary.known_spend, summary.interested_once)
    per_won = cost_per(summary.known_spend, summary.won_once)
    if per_lead is not None:
        lines.append(f"Est. list cost / discovered lead: {summary.currency} {per_lead}")
    if per_high is not None:
        lines.append(
            f"Est. list cost / high-opportunity lead: {summary.currency} {per_high}"
        )
    if per_interest is not None:
        lines.append(
            f"Est. list cost / historically interested: {summary.currency} {per_interest} "
            "(operational correlation, not ROI)"
        )
    if per_won is not None:
        lines.append(
            f"Est. list cost / historically won: {summary.currency} {per_won} "
            "(operational correlation, not ROI)"
        )
    return "\n".join(lines)
