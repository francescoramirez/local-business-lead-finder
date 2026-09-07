from __future__ import annotations

from leadfinder.fields import billing_sku_for_field_mask, billing_tier_for_mask, get_field_profile


def test_enterprise_profile_includes_website() -> None:
    profile = get_field_profile("enterprise")
    assert "places.websiteUri" in profile.mask
    assert "places.nationalPhoneNumber" in profile.mask
    assert profile.billing_tier == "Text Search Enterprise"


def test_dropping_phone_does_not_leave_enterprise_if_website_remains() -> None:
    mask = "places.id,places.displayName,places.websiteUri,nextPageToken"
    assert billing_tier_for_mask(mask) == "Text Search Enterprise"


def test_pro_profile_does_not_request_website() -> None:
    profile = get_field_profile("pro")
    assert "websiteUri" not in profile.mask
    assert billing_tier_for_mask(profile.mask) == "Text Search Pro"


def test_essentials_is_id_only() -> None:
    profile = get_field_profile("essentials")
    assert profile.mask == "places.id,places.name,nextPageToken"
    assert billing_tier_for_mask(profile.mask) == "Text Search Essentials (IDs Only)"
    assert billing_sku_for_field_mask(profile.mask) == "text_search_essentials_ids_only"
    assert billing_sku_for_field_mask("places.id") == "text_search_essentials_ids_only"
