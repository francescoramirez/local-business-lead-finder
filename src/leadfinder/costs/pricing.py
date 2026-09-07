"""Versioned Places Text Search (New) list-price catalog. Offline only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from leadfinder.fields import (
    SKU_ENTERPRISE,
    SKU_ENTERPRISE_ATMOSPHERE,
    SKU_ESSENTIALS_IDS_ONLY,
    SKU_LABELS,
    SKU_PRO,
)

# List-price model for the first PAYG band of Text Search (New) SKUs.
# reference_date is when this table's rates were published in Google docs LeadFinder
# modeled; verified_at is when this catalog was last checked in-repo. Neither is a
# guarantee that Google still bills these amounts.
CATALOG_VERSION = "google_places_text_search_new_2026_08"
PRICING_REFERENCE_DATE = "2025-03-01"
VERIFIED_AT = "2026-09-06"
CURRENCY = "USD"
SOURCE = (
    "Estimated Google Places Text Search (New) list prices for the first PAYG band. "
    "Not an invoice and not actual billed cost. LeadFinder does not read Google Cloud "
    "Billing and does not subtract monthly free usage, subscriptions, credits, volume "
    "discounts, taxes, other projects, or retries."
)

# USD list price per 1,000 requests. Essentials IDs Only is listed as no-cost on the
# public table; that is a list-price of 0, not a computed free-tier remainder.
LIST_RATES_PER_THOUSAND: dict[str, Decimal] = {
    SKU_ESSENTIALS_IDS_ONLY: Decimal("0.00"),
    SKU_PRO: Decimal("32.00"),
    SKU_ENTERPRISE: Decimal("35.00"),
    SKU_ENTERPRISE_ATMOSPHERE: Decimal("40.00"),
}


@dataclass(frozen=True)
class PricingCatalog:
    version: str
    reference_date: str
    verified_at: str
    currency: str
    source: str
    rates_per_thousand: dict[str, Decimal]
    sku_labels: dict[str, str]

    @property
    def effective_date(self) -> str:
        """Alias of reference_date. Not 'effective forever'."""
        return self.reference_date


def default_catalog() -> PricingCatalog:
    return PricingCatalog(
        version=CATALOG_VERSION,
        reference_date=PRICING_REFERENCE_DATE,
        verified_at=VERIFIED_AT,
        currency=CURRENCY,
        source=SOURCE,
        rates_per_thousand=dict(LIST_RATES_PER_THOUSAND),
        sku_labels=dict(SKU_LABELS),
    )


def rate_for_sku(sku: str, catalog: PricingCatalog | None = None) -> Decimal | None:
    book = catalog or default_catalog()
    return book.rates_per_thousand.get(sku.strip().lower())


def rate_for_profile(profile: str, catalog: PricingCatalog | None = None) -> Decimal | None:
    """Look up list rate via the profile's field mask SKU, never via the profile name."""
    from leadfinder.errors import ConfigError
    from leadfinder.fields import billing_sku_for_profile

    try:
        sku = billing_sku_for_profile(profile)
    except ConfigError:
        return None
    return rate_for_sku(sku, catalog)
