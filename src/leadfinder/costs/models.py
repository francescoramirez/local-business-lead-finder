from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

LIST_COST_DISCLAIMER = (
    "Estimated list-price cost only. Does not account for monthly free usage, "
    "subscriptions, credits, volume discounts, taxes, other projects, or retries. "
    "LeadFinder does not read Google Cloud Billing. Actual billed cost may differ."
)


@dataclass(frozen=True)
class CostEstimate:
    """List-price estimate of Places Text Search usage. Never an invoice."""

    status: str  # known | unknown | partial
    request_count: int
    field_profile: str
    currency: str
    amount: Decimal | None
    pricing_version: str
    detail: str = ""
    billing_sku: str = ""
    list_rate: Decimal | None = None

    @property
    def known(self) -> bool:
        return self.status == "known" and self.amount is not None

    @property
    def list_cost_estimate(self) -> Decimal | None:
        return self.amount


def format_estimate(estimate: CostEstimate) -> str:
    if estimate.status == "unknown" or estimate.amount is None:
        return "Estimated list cost: Unknown"
    quantized = estimate.amount.quantize(Decimal("0.01"))
    prefix = "at least " if estimate.status == "partial" else ""
    return f"Estimated list cost: {prefix}{estimate.currency} {quantized}"


@dataclass(frozen=True)
class CampaignCostSummary:
    campaign_id: int
    request_count: int
    known_spend: Decimal | None
    unknown_runs: int
    discovered_leads: int
    high_opportunity_leads: int
    interested_once: int
    won_once: int
    currency: str
    pricing_version: str
    status: str
