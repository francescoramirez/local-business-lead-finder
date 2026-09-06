from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from leadfinder.config import SearchConfig
from leadfinder.exporters import export_leads
from leadfinder.filtering import apply_filters
from leadfinder.geography import build_query
from leadfinder.models import Lead, SearchPlan, SearchReport, utc_now_iso
from leadfinder.normalize import place_to_lead
from leadfinder.persist import PlaceIdStore
from leadfinder.places_client import PlacesClient
from leadfinder.scoring import score_leads
from leadfinder.website import analyze_lead_website

ProgressFn = Callable[[str], None]


def build_plan(config: SearchConfig) -> SearchPlan:
    return config.to_plan()


def run_search(
    config: SearchConfig,
    client: PlacesClient,
    *,
    progress: ProgressFn | None = None,
    analyze: Callable[[Lead], Lead] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> SearchReport:
    plan = build_plan(config)
    seen_store = PlaceIdStore(config.seen_ids_path)
    checked: dict[str, Lead] = {}
    query_cache: dict[str, list[dict[str, Any]]] = {}
    api_requests = 0
    cache_hits = 0
    places_found = 0
    duplicates = 0
    queries_executed = 0
    fetched_at = utc_now_iso()
    analyzer = analyze or (analyze_lead_website if plan.analyze_websites else None)
    sleep = sleeper or time.sleep

    for location in plan.locations:
        for term in plan.search_terms:
            if api_requests >= config.max_requests:
                if progress:
                    progress("Stopped at --max-requests safety limit.")
                break
            query = build_query(term, location, region=plan.region, country=plan.country)
            cache_key = (
                f"{query}|type={plan.included_type}|pages={plan.pages}"
                f"|size={plan.page_size}|fields={plan.field_profile}"
            )
            queries_executed += 1
            if progress:
                progress(f"{query}")
            if cache_key in query_cache:
                places = query_cache[cache_key]
                cache_hits += 1
            else:
                remaining = config.max_requests - api_requests
                result = client.search_text(
                    text_query=query,
                    field_mask=plan.field_mask,
                    page_size=plan.page_size,
                    max_pages=min(plan.pages, remaining),
                    language_code=plan.language_code,
                    region_code=plan.country,
                    included_type=plan.included_type,
                    remaining_requests=remaining,
                )
                api_requests += result.api_requests
                places = result.places
                query_cache[cache_key] = places
                if config.delay:
                    sleep(config.delay)
            places_found += len(places)
            for place in places:
                place_id = str(place.get("id") or "").strip()
                if not place_id:
                    continue
                if place_id in checked:
                    duplicates += 1
                    continue
                lead = place_to_lead(
                    place,
                    source_query=query,
                    location=location,
                    search_term=term,
                    business_preset=plan.business,
                    place_type=plan.included_type,
                    country=plan.country,
                    region=plan.region,
                    fetched_at=fetched_at,
                )
                if analyzer:
                    analyzer(lead)
                checked[place_id] = lead
                seen_store.add(place_id)
        else:
            continue
        break

    scored = score_leads(list(checked.values()))
    leads = apply_filters(
        scored,
        include_closed=plan.include_closed,
        only_no_website=plan.only_no_website,
    )
    seen_store.save()
    return SearchReport(
        leads=leads,
        queries_executed=queries_executed,
        api_requests=api_requests,
        cache_hits=cache_hits,
        places_found=places_found,
        duplicates_discarded=duplicates,
        operational=sum(1 for lead in leads if lead.operational),
        no_website=sum(1 for lead in leads if not lead.has_website),
        contactable=sum(1 for lead in leads if lead.contactable),
    )


def export_report(report: SearchReport, config: SearchConfig, stamp: str) -> SearchReport:
    paths = export_leads(
        report.leads,
        output=config.output,
        formats=config.formats,
        stamp=stamp,
        force=config.force,
    )
    report.output_paths = [str(path) for path in paths]
    return report
