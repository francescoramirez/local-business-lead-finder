from __future__ import annotations

from collections.abc import Iterable

from leadfinder.models import Lead

CLOSED_PERMANENTLY = "CLOSED_PERMANENTLY"
CLOSED_TEMPORARILY = "CLOSED_TEMPORARILY"
OPERATIONAL = "OPERATIONAL"


def is_operational(lead: Lead) -> bool:
    status = (lead.business_status or "").upper()
    return status in {"", OPERATIONAL}


def has_website(lead: Lead) -> bool:
    return bool(lead.website.strip())


def no_website(lead: Lead) -> bool:
    return not has_website(lead)


def is_contactable(lead: Lead) -> bool:
    return bool(lead.phone.strip())


def not_contactable(lead: Lead) -> bool:
    return not is_contactable(lead)


def annotate_flags(lead: Lead) -> Lead:
    lead.has_website = has_website(lead)
    lead.contactable = is_contactable(lead)
    lead.operational = is_operational(lead)
    if not lead.website:
        lead.website_status = "no_website"
    elif lead.website_status in {"", "con_sitio"}:
        lead.website_status = "has_website"
    return lead


def apply_filters(
    leads: Iterable[Lead],
    *,
    include_closed: bool = False,
    only_no_website: bool = False,
) -> list[Lead]:
    results: list[Lead] = []
    for lead in leads:
        annotate_flags(lead)
        if not include_closed and lead.business_status.upper() == CLOSED_PERMANENTLY:
            continue
        if only_no_website and lead.has_website:
            continue
        results.append(lead)
    return results
