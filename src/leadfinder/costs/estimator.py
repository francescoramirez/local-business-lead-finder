"""Estimate Places Text Search list-price from completed page requests. No network."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from leadfinder.costs.models import CostEstimate
from leadfinder.costs.pricing import PricingCatalog, default_catalog, rate_for_sku
from leadfinder.errors import ConfigError
from leadfinder.fields import SKU_LABELS, billing_sku_for_field_mask, billing_sku_for_profile
from leadfinder.models import SearchPlan

# List-price math uses completed Text Search page requests (`api_requests` /
# logical_api_requests). HTTP retry attempts inside PlacesClient._post are counted
# separately as http_attempts and are not included here.


def estimate_sku(
    request_count: int,
    billing_sku: str,
    *,
    field_profile: str = "",
    catalog: PricingCatalog | None = None,
) -> CostEstimate:
    book = catalog or default_catalog()
    if request_count < 0:
        request_count = 0
    sku = billing_sku.strip().lower()
    rate = rate_for_sku(sku, book)
    if rate is None or not sku:
        return CostEstimate(
            status="unknown",
            request_count=request_count,
            field_profile=field_profile,
            currency=book.currency,
            amount=None,
            pricing_version=book.version,
            detail="No list rate for this billing SKU in the local catalog.",
            billing_sku=sku,
            list_rate=None,
        )
    amount = (rate * Decimal(request_count) / Decimal(1000)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    label = book.sku_labels.get(sku, SKU_LABELS.get(sku, sku))
    return CostEstimate(
        status="known",
        request_count=request_count,
        field_profile=field_profile,
        currency=book.currency,
        amount=amount,
        pricing_version=book.version,
        detail=f"{label}. {book.source}",
        billing_sku=sku,
        list_rate=rate,
    )


def estimate_requests(request_count: int, field_profile: str) -> CostEstimate:
    return estimate_requests_with_catalog(request_count, field_profile, default_catalog())


def estimate_requests_with_catalog(
    request_count: int,
    field_profile: str,
    catalog: PricingCatalog,
) -> CostEstimate:
    try:
        sku = billing_sku_for_profile(field_profile)
    except ConfigError:
        return CostEstimate(
            status="unknown",
            request_count=max(request_count, 0),
            field_profile=field_profile,
            currency=catalog.currency,
            amount=None,
            pricing_version=catalog.version,
            detail="Unknown field profile; cannot derive a billing SKU from a field mask.",
        )
    return estimate_sku(
        request_count, sku, field_profile=field_profile, catalog=catalog
    )


def estimate_plan(plan: SearchPlan, catalog: PricingCatalog | None = None) -> CostEstimate:
    book = catalog or default_catalog()
    sku = (
        billing_sku_for_field_mask(plan.field_mask)
        if plan.field_mask.strip()
        else billing_sku_for_profile(plan.field_profile)
    )
    return estimate_sku(
        plan.max_api_requests,
        sku,
        field_profile=plan.field_profile,
        catalog=book,
    )


def page_scenarios(
    *,
    query_count: int,
    max_requests: int,
    field_profile: str,
) -> list[tuple[int, int, CostEstimate]]:
    """Compare 1/2/3 pages against the same query count and request cap. No network."""
    rows: list[tuple[int, int, CostEstimate]] = []
    queries = max(query_count, 0)
    cap = max(max_requests, 1)
    for pages in (1, 2, 3):
        requests = min(cap, queries * pages) if queries else 0
        rows.append((pages, requests, estimate_requests(requests, field_profile)))
    return rows


def cost_per(numerator: Decimal | None, denominator: int) -> Decimal | None:
    if numerator is None or denominator <= 0:
        return None
    return (numerator / Decimal(denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
