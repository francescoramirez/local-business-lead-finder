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

SKU_ESSENTIALS_IDS_ONLY = "text_search_essentials_ids_only"
SKU_PRO = "text_search_pro"
SKU_ENTERPRISE = "text_search_enterprise"
SKU_ENTERPRISE_ATMOSPHERE = "text_search_enterprise_atmosphere"

SKU_LABELS = {
    SKU_ESSENTIALS_IDS_ONLY: "Text Search Essentials (IDs Only)",
    SKU_PRO: "Text Search Pro",
    SKU_ENTERPRISE: "Text Search Enterprise",
    SKU_ENTERPRISE_ATMOSPHERE: "Text Search Enterprise + Atmosphere",
}

_ATMOSPHERE_FIELDS = frozenset(
    {
        "reviews",
        "editorialsummary",
        "generativesummary",
        "reviewsummary",
        "dinein",
        "takeout",
        "places.reviews",
        "places.editorialsummary",
        "places.generativesummary",
        "places.reviewsummary",
        "places.dinein",
        "places.takeout",
    }
)
_ENTERPRISE_FIELDS = frozenset(
    {
        "websiteuri",
        "nationalphonenumber",
        "internationalphonenumber",
        "rating",
        "userratingcount",
        "regularopeninghours",
        "currentopeninghours",
        "pricelevel",
        "pricerange",
        "places.websiteuri",
        "places.nationalphonenumber",
        "places.internationalphonenumber",
        "places.rating",
        "places.userratingcount",
        "places.regularopeninghours",
        "places.currentopeninghours",
        "places.pricelevel",
        "places.pricerange",
    }
)
_PRO_FIELDS = frozenset(
    {
        "displayname",
        "formattedaddress",
        "googlemapsuri",
        "businessstatus",
        "types",
        "primarytype",
        "places.displayname",
        "places.formattedaddress",
        "places.googlemapsuri",
        "places.businessstatus",
        "places.types",
        "places.primarytype",
    }
)


def get_field_profile(name: str) -> FieldProfile:
    key = name.strip().lower()
    if key not in FIELD_PROFILES:
        known = ", ".join(sorted(FIELD_PROFILES))
        raise ConfigError(f"Unknown field profile '{name}'. Choose one of: {known}.")
    return FIELD_PROFILES[key]


def _mask_tokens(mask: str) -> set[str]:
    tokens: set[str] = set()
    for item in mask.split(","):
        raw = item.strip()
        if not raw:
            continue
        lowered = raw.casefold()
        tokens.add(lowered)
        tokens.add(lowered.rsplit(".", 1)[-1])
    return tokens


def billing_sku_for_field_mask(fields: str) -> str:
    """Highest Text Search (New) SKU required by any requested field. Not a profile name."""
    tokens = _mask_tokens(fields)
    if tokens & _ATMOSPHERE_FIELDS:
        return SKU_ENTERPRISE_ATMOSPHERE
    if tokens & _ENTERPRISE_FIELDS:
        return SKU_ENTERPRISE
    if tokens & _PRO_FIELDS:
        return SKU_PRO
    return SKU_ESSENTIALS_IDS_ONLY


def billing_sku_for_profile(name: str) -> str:
    return billing_sku_for_field_mask(get_field_profile(name).mask)


def billing_tier_for_mask(mask: str) -> str:
    return SKU_LABELS[billing_sku_for_field_mask(mask)]
