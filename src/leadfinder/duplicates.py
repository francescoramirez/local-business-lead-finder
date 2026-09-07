"""Conservative duplicate hints. Never merges. Phone/domain only when already in memory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from leadfinder.models import LocalLeadState, ManagedLead

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
GENERIC_NAMES = frozenset(
    {
        "cafe",
        "hotel",
        "restaurant",
        "bakery",
        "gym",
        "bar",
        "kiosco",
        "farmacia",
        "shop",
        "store",
    }
)


@dataclass(frozen=True)
class DuplicateMatch:
    reason: str
    confidence: str
    other_place_id: str
    other_label: str
    source: str  # session | local

    def as_text(self) -> str:
        lines = ["Possible duplicate", self.reason]
        if self.other_label:
            lines.append(f'Previously seen as "{self.other_label}"')
        return "\n".join(lines)


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


def _name_key_ok(name: str) -> bool:
    if not name or name in GENERIC_NAMES:
        return False
    tokens = name.split()
    if len(tokens) == 1 and len(name) < 5:
        return False
    return True


def find_duplicates(
    item: ManagedLead,
    *,
    session: list[ManagedLead],
    local: list[LocalLeadState] | None = None,
) -> list[DuplicateMatch]:
    """Session uses in-memory phone/website. Local store only has label + locality."""
    lead = item.lead
    phone = normalize_phone(lead.phone)
    domain = website_domain(lead.website or lead.final_url)
    name = normalize_name(lead.name)
    locality = (lead.source_location or "").casefold().strip()
    matches: list[DuplicateMatch] = []
    seen_ids = {lead.place_id}

    phones: dict[str, ManagedLead] = {}
    domains: dict[str, ManagedLead] = {}
    session_names: dict[tuple[str, str], ManagedLead] = {}
    for other in session:
        if other.lead.place_id in seen_ids:
            continue
        other_phone = normalize_phone(other.lead.phone)
        if other_phone and len(other_phone) >= 8:
            phones.setdefault(other_phone, other)
        other_domain = website_domain(other.lead.website or other.lead.final_url)
        if other_domain and other_domain not in _SOCIAL_HOSTS:
            domains.setdefault(other_domain, other)
        other_name = normalize_name(other.lead.name)
        other_loc = (other.lead.source_location or "").casefold().strip()
        if _name_key_ok(other_name) and other_loc:
            session_names.setdefault((other_name, other_loc), other)

    if phone and len(phone) >= 8 and phone in phones:
        other = phones[phone]
        matches.append(
            DuplicateMatch(
                "Same phone",
                "strong",
                other.lead.place_id,
                other.lead.name or other.label,
                "session",
            )
        )
        seen_ids.add(other.lead.place_id)
    if domain and domain not in _SOCIAL_HOSTS and domain in domains:
        other = domains[domain]
        if other.lead.place_id not in seen_ids:
            matches.append(
                DuplicateMatch(
                    "Same website domain",
                    "strong",
                    other.lead.place_id,
                    other.lead.name or other.label,
                    "session",
                )
            )
            seen_ids.add(other.lead.place_id)
    if _name_key_ok(name) and locality and (name, locality) in session_names:
        other = session_names[(name, locality)]
        if other.lead.place_id not in seen_ids:
            matches.append(
                DuplicateMatch(
                    "Same name and locality",
                    "moderate",
                    other.lead.place_id,
                    other.lead.name or other.label,
                    "session",
                )
            )
            seen_ids.add(other.lead.place_id)

    name_index: dict[tuple[str, str], LocalLeadState] = {}
    for state in local or ():
        if state.place_id in seen_ids:
            continue
        key = (normalize_name(state.label), (state.source_location or "").casefold().strip())
        if _name_key_ok(key[0]) and key[1]:
            name_index.setdefault(key, state)
    if _name_key_ok(name) and locality and (name, locality) in name_index:
        state = name_index[(name, locality)]
        matches.append(
            DuplicateMatch(
                "Same name and locality",
                "moderate",
                state.place_id,
                state.label,
                "local",
            )
        )
    return matches


def duplicate_hint(item: ManagedLead, session: list[ManagedLead]) -> str:
    matches = find_duplicates(item, session=session, local=None)
    return matches[0].as_text() if matches else ""


def duplicate_hint_text(
    item: ManagedLead,
    session: list[ManagedLead],
    local: list[LocalLeadState] | None = None,
) -> str:
    matches = find_duplicates(item, session=session, local=local)
    return matches[0].as_text() if matches else ""
