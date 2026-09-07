"""Conservative in-session duplicate hints. Never merges records."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from leadfinder.models import ManagedLead

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SOCIAL_HOSTS = frozenset(
    {
        "facebook.com",
        "www.facebook.com",
        "instagram.com",
        "www.instagram.com",
        "x.com",
        "twitter.com",
        "www.twitter.com",
        "linktr.ee",
        "linktree.com",
    }
)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def normalize_name(name: str) -> str:
    text = (name or "").casefold().strip()
    text = _NON_ALNUM.sub(" ", text)
    return " ".join(text.split())


def website_domain(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    host = urlparse(raw).hostname or ""
    host = host.casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


def duplicate_hint(item: ManagedLead, session: list[ManagedLead]) -> str:
    """Return a short hint or empty string. Conservative: exact phone/domain/name+locality."""
    lead = item.lead
    phone = normalize_phone(lead.phone)
    domain = website_domain(lead.website or lead.final_url)
    name = normalize_name(lead.name)
    locality = (lead.source_location or "").casefold().strip()
    for other in session:
        if other.lead.place_id == lead.place_id:
            continue
        other_phone = normalize_phone(other.lead.phone)
        if phone and len(phone) >= 8 and phone == other_phone:
            return "Possible duplicate"
        other_domain = website_domain(other.lead.website or other.lead.final_url)
        if (
            domain
            and other_domain
            and domain == other_domain
            and domain not in _SOCIAL_HOSTS
        ):
            return "Possible duplicate"
        other_name = normalize_name(other.lead.name)
        other_loc = (other.lead.source_location or "").casefold().strip()
        if name and locality and name == other_name and locality == other_loc:
            return "Possible duplicate"
    return ""
