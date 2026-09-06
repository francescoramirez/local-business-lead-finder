from __future__ import annotations

from dataclasses import dataclass

from leadfinder.errors import ConfigError

ESSENTIALS_FIELDS = (
    "places.id",
    "places.name",
    "nextPageToken",
)

PRO_FIELDS = (
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.googleMapsUri",
    "places.businessStatus",
    "places.types",
    "places.primaryType",
    "nextPageToken",
)

# websiteUri is Text Search Enterprise. Phone, rating, and userRatingCount
# are the same SKU, so the default profile includes them without raising the tier.
ENTERPRISE_FIELDS = (
    *PRO_FIELDS[:-1],
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "nextPageToken",
)


@dataclass(frozen=True)
class FieldProfile:
    name: str
    mask: str
    billing_tier: str
    description: str


FIELD_PROFILES: dict[str, FieldProfile] = {
    "essentials": FieldProfile(
        name="essentials",
        mask=",".join(ESSENTIALS_FIELDS),
        billing_tier="Text Search Essentials (IDs Only)",
        description="Place IDs only. Not enough to score website opportunities.",
    ),
    "pro": FieldProfile(
        name="pro",
        mask=",".join(PRO_FIELDS),
        billing_tier="Text Search Pro",
        description="Name, address, status, types, and Maps URL. No website or phone.",
    ),
    "enterprise": FieldProfile(
        name="enterprise",
        mask=",".join(ENTERPRISE_FIELDS),
        billing_tier="Text Search Enterprise",
        description=(
            "Adds websiteUri, phone, rating, and userRatingCount. "
            "websiteUri alone already bills Enterprise; dropping phone does not lower the SKU."
        ),
    ),
}

DEFAULT_FIELD_PROFILE = "enterprise"


def get_field_profile(name: str) -> FieldProfile:
    key = name.strip().lower()
    if key not in FIELD_PROFILES:
        known = ", ".join(sorted(FIELD_PROFILES))
        raise ConfigError(f"Unknown field profile '{name}'. Choose one of: {known}.")
    return FIELD_PROFILES[key]


def billing_tier_for_mask(mask: str) -> str:
    fields = {item.strip() for item in mask.split(",") if item.strip()}
    atmosphere = {
        "places.reviews",
        "places.editorialSummary",
        "places.generativeSummary",
        "places.reviewSummary",
        "places.dineIn",
        "places.takeout",
    }
    enterprise = {
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.rating",
        "places.userRatingCount",
        "places.regularOpeningHours",
        "places.currentOpeningHours",
        "places.priceLevel",
        "places.priceRange",
    }
    if fields & atmosphere:
        return "Text Search Enterprise + Atmosphere"
    if fields & enterprise:
        return "Text Search Enterprise"
    pro = {
        "places.displayName",
        "places.formattedAddress",
        "places.googleMapsUri",
        "places.businessStatus",
        "places.types",
        "places.primaryType",
    }
    if fields & pro:
        return "Text Search Pro"
    return "Text Search Essentials (IDs Only)"
