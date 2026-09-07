from __future__ import annotations

from pathlib import Path

import pytest

from leadfinder.application.service import LeadService, matches_filters
from leadfinder.duplicates import duplicate_hint
from leadfinder.models import Lead, ManagedLead
from leadfinder.storage.local_leads import LocalLeadStore


def _lead(**overrides: object) -> Lead:
    values = dict(
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
        region="",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    values.update(overrides)
    return Lead(**values)  # type: ignore[arg-type]


def test_transaction_rollback_keeps_notes(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "tx.db")
    store.mark_seen("ChIJ_TX")
    try:
        with store.transaction():
            store.set_notes("ChIJ_TX", "should not stick", commit=False)
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    state = store.get("ChIJ_TX")
    assert state is not None
    assert state.notes == ""
    store.close()


def test_status_and_activity_atomic_on_success(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "st.db")
    store.mark_seen("ChIJ_ST")
    store.set_contact_status("ChIJ_ST", "contacted")
    acts = store.list_activities("ChIJ_ST")
    assert any(item.activity_type == "status_change" for item in acts)
    assert store.get("ChIJ_ST").contact_status == "contacted"  # type: ignore[union-attr]
    store.close()


def test_manual_priority_persists_and_is_not_opportunity(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "pr.db")
    service = LeadService(store)
    store.mark_seen("ChIJ_PR", opportunity_level="high", opportunity_score=80)
    state = store.set_manual_priority("ChIJ_PR", "low")
    assert state.manual_priority == "low"
    assert state.opportunity_level == "high"
    item = ManagedLead(lead=_lead(place_id="ChIJ_PR"), manual_priority="normal")
    updated = service.set_priority(item, "ignore")
    assert updated.manual_priority == "ignore"
    assert matches_filters(updated, manual_priority="ignore")
    assert not matches_filters(updated, manual_priority="high")
    store.close()


def test_duplicate_hints_conservative() -> None:
    a = ManagedLead(lead=_lead(place_id="1", phone="+54 11 5555 1234"))
    b = ManagedLead(lead=_lead(place_id="2", phone="011 5555-1234", name="Other"))
    c = ManagedLead(
        lead=_lead(
            place_id="3",
            phone="",
            name="Panaderia Sur",
            website="https://other.example",
            source_location="Harbor",
        )
    )
    d = ManagedLead(
        lead=_lead(
            place_id="4",
            name="Cafe Norte",
            phone="",
            website="",
            source_location="Example City",
        )
    )
    e = ManagedLead(
        lead=_lead(
            place_id="5",
            name="Cafe Norte",
            phone="",
            website="",
            source_location="Other Town",
        )
    )
    session = [a, b, c, d, e]
    assert duplicate_hint(a, session) == "Possible duplicate"
    assert duplicate_hint(c, session) == ""
    assert duplicate_hint(d, session) == "Possible duplicate"
    assert duplicate_hint(e, session) == ""
    same_name_city = ManagedLead(
        lead=_lead(
            place_id="6",
            name="Cafe Norte",
            phone="",
            website="",
            source_location="Example City",
        )
    )
    assert duplicate_hint(same_name_city, session + [same_name_city]) == "Possible duplicate"


def test_empty_phone_is_not_a_duplicate() -> None:
    a = ManagedLead(lead=_lead(place_id="1", phone="", website=""))
    b = ManagedLead(lead=_lead(place_id="2", phone="", name="Different", website=""))
    assert duplicate_hint(a, [a, b]) == ""


def test_config_groq_env_centralized(monkeypatch: pytest.MonkeyPatch) -> None:
    from leadfinder.ai.provider import groq_model
    from leadfinder.config import groq_api_key, groq_model_from_env

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    assert groq_api_key() == ""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testfakekey1234567890")
    monkeypatch.setenv("GROQ_MODEL", "custom-model")
    assert groq_api_key() == "gsk_testfakekey1234567890"
    assert groq_model_from_env() == "custom-model"
    assert groq_model() == "custom-model"
    assert groq_model("override") == "override"
