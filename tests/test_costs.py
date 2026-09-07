from __future__ import annotations

from decimal import Decimal

from leadfinder.costs.aggregation import (
    estimate_from_run,
    format_campaign_costs,
    summarize_campaign_costs,
)
from leadfinder.costs.estimator import estimate_requests, estimate_sku
from leadfinder.costs.models import LIST_COST_DISCLAIMER, format_estimate
from leadfinder.costs.pricing import LIST_RATES_PER_THOUSAND, default_catalog
from leadfinder.fields import (
    SKU_ENTERPRISE,
    SKU_ENTERPRISE_ATMOSPHERE,
    SKU_ESSENTIALS_IDS_ONLY,
    SKU_PRO,
    billing_sku_for_field_mask,
    billing_sku_for_profile,
)
from leadfinder.models import SearchRun


def test_ids_only_mask_is_essentials() -> None:
    assert billing_sku_for_field_mask("places.id,nextPageToken") == SKU_ESSENTIALS_IDS_ONLY


def test_display_name_is_pro() -> None:
    assert billing_sku_for_field_mask("places.id,places.displayName") == SKU_PRO


def test_website_rating_phone_are_enterprise() -> None:
    assert billing_sku_for_field_mask("places.websiteUri") == SKU_ENTERPRISE
    assert billing_sku_for_field_mask("places.rating") == SKU_ENTERPRISE
    assert billing_sku_for_field_mask("places.userRatingCount") == SKU_ENTERPRISE
    assert billing_sku_for_field_mask("places.internationalPhoneNumber") == SKU_ENTERPRISE
    assert billing_sku_for_field_mask("places.nationalPhoneNumber") == SKU_ENTERPRISE


def test_reviews_are_enterprise_atmosphere() -> None:
    assert billing_sku_for_field_mask("places.reviews") == SKU_ENTERPRISE_ATMOSPHERE


def test_mixed_masks_take_highest_sku() -> None:
    assert (
        billing_sku_for_field_mask("places.displayName,places.websiteUri") == SKU_ENTERPRISE
    )
    assert (
        billing_sku_for_field_mask("places.websiteUri,places.reviews")
        == SKU_ENTERPRISE_ATMOSPHERE
    )


def test_product_profiles_map_to_skus_via_masks() -> None:
    assert billing_sku_for_profile("essentials") == SKU_ESSENTIALS_IDS_ONLY
    assert billing_sku_for_profile("pro") == SKU_PRO
    assert billing_sku_for_profile("enterprise") == SKU_ENTERPRISE


def test_list_rates_match_first_payg_band() -> None:
    assert LIST_RATES_PER_THOUSAND[SKU_ESSENTIALS_IDS_ONLY] == Decimal("0.00")
    assert LIST_RATES_PER_THOUSAND[SKU_PRO] == Decimal("32.00")
    assert LIST_RATES_PER_THOUSAND[SKU_ENTERPRISE] == Decimal("35.00")
    assert LIST_RATES_PER_THOUSAND[SKU_ENTERPRISE_ATMOSPHERE] == Decimal("40.00")


def test_profile_estimates_use_sku_not_profile_name() -> None:
    essentials = estimate_requests(1000, "essentials")
    pro = estimate_requests(1000, "pro")
    enterprise = estimate_requests(1000, "enterprise")
    assert essentials.amount == Decimal("0.00")
    assert essentials.billing_sku == SKU_ESSENTIALS_IDS_ONLY
    assert pro.amount == Decimal("32.00")
    assert pro.billing_sku == SKU_PRO
    assert enterprise.amount == Decimal("35.00")
    assert enterprise.billing_sku == SKU_ENTERPRISE
    atmos = estimate_sku(1000, SKU_ENTERPRISE_ATMOSPHERE)
    assert atmos.amount == Decimal("40.00")


def test_free_tier_is_not_subtracted() -> None:
    pro = estimate_requests(1000, "pro")
    assert pro.amount == Decimal("32.00")
    assert "free" not in format_estimate(pro).lower()


def test_list_cost_wording_never_claims_invoice() -> None:
    text = format_estimate(estimate_requests(18, "enterprise"))
    assert text == "Estimated list cost: USD 0.63"
    assert "actual" not in text.lower()
    assert "invoice" not in text.lower()
    assert "free usage" in LIST_COST_DISCLAIMER.lower()
    catalog = default_catalog()
    assert catalog.version == "google_places_text_search_new_2026_08"
    assert catalog.reference_date == "2025-03-01"
    assert catalog.verified_at == "2026-09-06"


def test_unknown_historical_run_without_usage() -> None:
    run = SearchRun(
        id=1,
        created_at="",
        business_preset="cafe",
        location="",
        region="",
        country="AR",
        lead_count=0,
        high_opportunity_count=0,
        cost_status="unknown",
    )
    assert estimate_from_run(run).status == "unknown"


def test_campaign_aggregation_mixed_skus() -> None:
    summary = summarize_campaign_costs(
        [
            SearchRun(
                id=1,
                created_at="",
                business_preset="cafe",
                location="",
                region="",
                country="AR",
                lead_count=1,
                high_opportunity_count=0,
                campaign_id=1,
                request_count=1000,
                billing_sku=SKU_PRO,
                field_profile="pro",
                cost_status="known",
            ),
            SearchRun(
                id=2,
                created_at="",
                business_preset="cafe",
                location="",
                region="",
                country="AR",
                lead_count=1,
                high_opportunity_count=0,
                campaign_id=1,
                request_count=1000,
                billing_sku=SKU_ENTERPRISE,
                field_profile="enterprise",
                cost_status="known",
            ),
        ],
        campaign_id=1,
        discovered_leads=2,
        high_opportunity_leads=0,
        interested_once=0,
        won_once=0,
    )
    assert summary.status == "known"
    assert summary.known_spend == Decimal("67.00")
    text = format_campaign_costs(summary)
    assert "Estimated list cost" in text
    assert "actual cost" not in text.lower()
    assert "invoice" in text.lower()
