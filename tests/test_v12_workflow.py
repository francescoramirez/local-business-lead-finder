from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from leadfinder.application.service import LeadService
from leadfinder.costs.aggregation import estimate_from_run, summarize_campaign_costs
from leadfinder.costs.estimator import cost_per, estimate_requests, page_scenarios
from leadfinder.costs.models import format_estimate
from leadfinder.duplicates import find_duplicates
from leadfinder.errors import ConfigError
from leadfinder.models import Lead, ManagedLead, SearchRun
from leadfinder.storage.local_leads import LocalLeadStore
from leadfinder.templates import render_template, values_from_lead
from leadfinder.undo import can_undo
from leadfinder.workspace import export_workspace, import_workspace


def _lead(**overrides: object) -> Lead:
    values: dict[str, object] = dict(
        place_id="ChIJ_A",
        name="Cafe Norte",
        phone="011 5555-1234",
        website="https://cafenorte.example",
        website_status="has_website",
        address="1 Main",
        business_status="OPERATIONAL",
        types="cafe",
        primary_type="cafe",
        google_maps_url="",
        rating=4.0,
        user_rating_count=10,
        lead_score=50,
        lead_reason="",
        has_website=True,
        contactable=True,
        operational=True,
        source_query="cafe",
        source_location="Example City",
        search_term="cafe",
        business_preset="cafe",
        place_type="cafe",
        country="AR",
        region="Buenos Aires",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    values.update(overrides)
    return Lead(**values)  # type: ignore[arg-type]


def test_status_undo_keeps_history(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "undo.db")
    service = LeadService(store)
    store.mark_seen("ChIJ_U1", label="Undo Cafe")
    item = ManagedLead(lead=_lead(place_id="ChIJ_U1"))
    item = service.set_status(item, "contacted")
    assert item.contact_status == "contacted"
    undone = service.undo_last(item)
    assert undone.contact_status == "new"
    types = [row.activity_type for row in store.list_activities("ChIJ_U1")]
    assert types.count("status_change") == 2
    inverse = [row for row in store.list_activities("ChIJ_U1") if row.reverses_activity_id]
    assert inverse
    store.close()


def test_stale_and_already_undone_rejected(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "stale.db")
    service = LeadService(store)
    store.mark_seen("ChIJ_U2")
    item = ManagedLead(lead=_lead(place_id="ChIJ_U2"))
    item = service.set_status(item, "contacted")
    first = next(
        row for row in store.list_activities("ChIJ_U2") if row.activity_type == "status_change"
    )
    item = service.set_status(item, "interested")
    state = store.get("ChIJ_U2")
    assert state is not None
    assert not can_undo(first, state, store.list_activities("ChIJ_U2"))
    item = service.undo_last(item)
    assert item.contact_status == "contacted"
    history = store.list_activities("ChIJ_U2")
    assert not can_undo(first, store.get("ChIJ_U2"), history)  # type: ignore[arg-type]
    second = next(
        row
        for row in history
        if row.activity_type == "status_change"
        and row.id != first.id
        and not row.reverses_activity_id
    )
    assert any(row.reverses_activity_id == second.id for row in history)
    store.close()


def test_follow_up_and_priority_undo(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "fp.db")
    service = LeadService(store)
    store.mark_seen("ChIJ_U3")
    item = ManagedLead(lead=_lead(place_id="ChIJ_U3"))
    item = service.set_follow_up(item, "2026-09-01T00:00:00+00:00")
    item = service.undo_last(item)
    assert item.next_follow_up_at == ""
    item = service.set_priority(item, "high")
    item = service.undo_last(item)
    assert item.manual_priority == "normal"
    store.close()


def test_undo_transaction_rollback(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "txu.db")
    service = LeadService(store)
    store.mark_seen("ChIJ_U4")
    item = ManagedLead(lead=_lead(place_id="ChIJ_U4"))
    item = service.set_status(item, "contacted")
    store._conn.execute(
        "UPDATE activities SET metadata_json = ? WHERE activity_type = ?",
        (
            '{"field":"contact_status","previous_value":"bogus","new_value":"contacted"}',
            "status_change",
        ),
    )
    store._conn.commit()
    with pytest.raises(ValueError):
        service.undo_last(item)
    state = store.get("ChIJ_U4")
    assert state is not None
    assert state.contact_status == "contacted"
    store.close()


def test_historical_duplicates_and_no_merge() -> None:
    session_a = ManagedLead(lead=_lead(place_id="1", phone="1155551234", website=""))
    session_b = ManagedLead(
        lead=_lead(place_id="2", phone="11 5555-1234", name="Other Spot", website="")
    )
    matches = find_duplicates(session_a, session=[session_a, session_b])
    assert any(item.reason == "Same phone" and item.confidence == "strong" for item in matches)
    generic = ManagedLead(
        lead=_lead(place_id="3", name="Cafe", phone="", website="", source_location="Example City")
    )
    twin = ManagedLead(
        lead=_lead(place_id="4", name="Cafe", phone="", website="", source_location="Example City")
    )
    assert find_duplicates(generic, session=[generic, twin]) == []
    other_city = ManagedLead(
        lead=_lead(
            place_id="5",
            name="Cafe Norte",
            phone="",
            website="",
            source_location="Other Town",
        )
    )
    assert find_duplicates(other_city, session=[session_a, other_city]) == []


def test_historical_name_locality_from_store(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "dup.db")
    store.mark_seen(
        "ChIJ_OLD",
        label="Harbor Needle Tailor",
        source_location="Example City",
    )
    current = ManagedLead(
        lead=_lead(
            place_id="ChIJ_NEW",
            name="Harbor Needle Tailor",
            phone="",
            website="",
            source_location="Example City",
        )
    )
    matches = find_duplicates(current, session=[current], local=store.list_all())
    assert matches
    assert matches[0].source == "local"
    assert "Same name and locality" in matches[0].reason
    store.close()


def test_templates_render_and_workspace(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "tpl.db")
    created = store.create_template(
        name="No website",
        body="Hola {business_name} in {location} missing {unknown}",
    )
    store.update_template(created.id, body="Hola {business_name} in {missing_place}")
    item = ManagedLead(lead=_lead(name="Amber Finch Bakery", source_location="Example Bay"))
    text = render_template(
        store.get_template(created.id).body,  # type: ignore[union-attr]
        values_from_lead(item),
    )
    assert "Amber Finch Bakery" in text
    assert "{missing_place}" in text
    rendered_braces = render_template("keep {__import__}", {"business_name": "X"})
    assert rendered_braces == "keep {__import__}"
    zip_path = tmp_path / "ws.zip"
    export_workspace(store, zip_path)
    dest = LocalLeadStore(tmp_path / "dst.db")
    dest.create_template(name="No website", body="existing")
    added = import_workspace(dest, zip_path)
    names = [item.name for item in dest.list_templates()]
    assert "No website" in names
    assert "No website (Imported)" in names
    assert added["templates"] == 1
    store.delete_template(created.id)
    assert store.list_templates() == []
    store.close()
    dest.close()


def test_ai_payload_includes_template_not_phone() -> None:
    from leadfinder.ai.service import assert_minimized, build_sales_prep_request

    item = ManagedLead(lead=_lead(phone="011 5555-0000", website="https://secret.example"))
    payload = build_sales_prep_request(
        item, language="Spanish", template_body="Hola {business_name}"
    ).to_payload()
    assert payload["selected_template"] == "Hola {business_name}"
    assert "phone" not in payload
    assert "website" not in payload
    assert_minimized(payload)


def test_cost_estimates_decimal_and_unknown() -> None:
    estimate = estimate_requests(18, "enterprise")
    assert estimate.known
    assert estimate.amount == Decimal("0.63")
    assert "USD 0.63" in format_estimate(estimate)
    assert "Estimated list cost" in format_estimate(estimate)
    assert "actual cost" not in format_estimate(estimate).lower()
    empty = estimate_requests(0, "enterprise")
    assert empty.amount == Decimal("0.00")
    unknown = estimate_requests_with_missing_profile()
    assert unknown.status == "unknown"
    assert cost_per(Decimal("1.00"), 0) is None
    old = SearchRun(
        id=1,
        created_at="",
        business_preset="cafe",
        location="",
        region="",
        country="AR",
        lead_count=3,
        high_opportunity_count=1,
        campaign_id=1,
        cost_status="unknown",
    )
    assert estimate_from_run(old).status == "unknown"
    summary = summarize_campaign_costs(
        [
            SearchRun(
                id=2,
                created_at="",
                business_preset="cafe",
                location="",
                region="",
                country="AR",
                lead_count=10,
                high_opportunity_count=2,
                campaign_id=1,
                request_count=10,
                field_profile="enterprise",
                estimated_cost="0.40",
                cost_status="known",
                currency="USD",
            ),
            old,
        ],
        campaign_id=1,
        discovered_leads=10,
        high_opportunity_leads=2,
        interested_once=0,
        won_once=0,
    )
    assert summary.status == "partial"
    pages = page_scenarios(query_count=4, max_requests=100, field_profile="enterprise")
    assert [row[0] for row in pages] == [1, 2, 3]
    assert pages[0][1] == 4
    assert pages[2][1] == 12


def estimate_requests_with_missing_profile():
    return estimate_requests(10, "not-a-profile")


def test_retry_http_not_counted_in_api_requests() -> None:
    """Cost uses completed Text Search calls. Failed retry attempts inside _post are not counted."""
    from leadfinder.places_client import PlacesClient
    from tests.http import FakeResponse
    from tests.test_client_retry import _http_error

    calls = {"count": 0}

    def opener(request: object, timeout: float = 0) -> FakeResponse:
        calls["count"] += 1
        if calls["count"] < 3:
            raise _http_error(503)
        return FakeResponse({"places": []})

    client = PlacesClient("test-key", opener=opener, sleep=lambda _: None, max_retries=4)
    result = client.search_text(
        text_query="x",
        field_mask="places.id",
        page_size=1,
        max_pages=1,
        language_code="en",
        region_code="US",
    )
    assert calls["count"] == 3
    assert result.api_requests == 1
    assert result.http_attempts == 3


def test_demo_data_refuses_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from leadfinder.demo import seed_demo_database

    target = tmp_path / "demo.db"
    written = seed_demo_database(target, count=50)
    assert written.exists()
    store = LocalLeadStore(written)
    assert len(store.list_all()) >= 50
    store.close()
    monkeypatch.setattr("leadfinder.demo.default_db_path", lambda: target)
    with pytest.raises(ConfigError):
        seed_demo_database(target)


def test_saved_filters_merge_names() -> None:
    from leadfinder.gui.saved_filters import merge_imported_filters

    merged = merge_imported_filters(
        {"Best prospects": {"status": "new"}},
        {"Best prospects": {"status": "contacted"}},
    )
    assert "Best prospects" in merged
    assert merged["Best prospects (Imported)"]["status"] == "contacted"


def test_duplicate_lookup_scale(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "scale.db")
    with store.transaction():
        for index in range(3000):
            store.mark_seen(
                f"ChIJ_S{index}",
                label=f"Studio {index}",
                source_location="Example City",
                commit=False,
            )
            store.record_search(
                business_preset="cafe",
                location="Example City",
                region="",
                country="AR",
                lead_count=1,
                high_opportunity_count=0,
                campaign_id=0,
                request_count=1,
                field_profile="enterprise",
                estimated_cost="0.04",
                cost_status="known",
                currency="USD",
                commit=False,
            )
    current = ManagedLead(
        lead=_lead(
            place_id="probe",
            name="Studio 12",
            phone="",
            website="",
            source_location="Example City",
        )
    )
    matches = find_duplicates(current, session=[current], local=store.list_all())
    assert matches
    summary = summarize_campaign_costs(
        store.list_searches(limit=0),
        campaign_id=0,
        discovered_leads=3000,
        high_opportunity_leads=1,
        interested_once=0,
        won_once=0,
    )
    assert summary.request_count == 3000
    store.close()
