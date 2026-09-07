"""Manual pitch templates. Explicit placeholder substitution; never eval."""

from __future__ import annotations

import re
from dataclasses import dataclass

PLACEHOLDERS: tuple[str, ...] = (
    "business_name",
    "business_type",
    "location",
    "region",
    "country",
    "presence_type",
    "opportunity_level",
)

_TOKEN = re.compile(r"\{([a-z_]+)\}")


@dataclass
class PitchTemplate:
    id: int
    name: str
    body: str
    created_at: str
    updated_at: str
    business_type: str = ""
    presence_type: str = ""
    language: str = ""


def render_template(body: str, values: dict[str, str]) -> str:
    """Replace known placeholders. Missing or unknown tokens stay visible."""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in PLACEHOLDERS:
            return match.group(0)
        value = str(values.get(key) or "").strip()
        if not value:
            return match.group(0)
        return value

    return _TOKEN.sub(replace, body)


def values_from_lead(item: object) -> dict[str, str]:
    from leadfinder.labels import OPPORTUNITY_LABELS, PRESENCE_LABELS
    from leadfinder.models import ManagedLead

    if not isinstance(item, ManagedLead):
        return {}
    lead = item.lead
    return {
        "business_name": lead.name or item.label,
        "business_type": lead.primary_type or lead.place_type or lead.business_preset,
        "location": lead.source_location,
        "region": lead.region,
        "country": lead.country,
        "presence_type": PRESENCE_LABELS.get(lead.website_status, lead.website_status),
        "opportunity_level": OPPORTUNITY_LABELS.get(
            lead.opportunity_level, lead.opportunity_level
        ),
    }
