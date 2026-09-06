from __future__ import annotations

from pathlib import Path
from typing import Any

from leadfinder.application.service import LeadService, matches_filters, merge_local_state
from leadfinder.config import SearchConfig
from leadfinder.normalize import place_to_lead
from leadfinder.places_client import TextSearchResult
from leadfinder.scoring import score_lead
from leadfinder.storage.local_leads import LocalLeadStore
from tests.conftest import synthetic_place


def _lead(place_id: str, name: str, **kwargs):
    return score_lead(
        place_to_lead(
            synthetic_place(place_id, name, **kwargs),
            source_query="cafe en Example City",
            location="Example City",
            search_term="cafe",
            business_preset="cafe",
            place_type="cafe",
            country="AR",
            region="",
        )
    )


def test_merge_marks_duplicates_and_restores_status(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    store.set_contact_status("ChIJ_SYNTHETIC_210", "follow_up")
    store.set_notes("ChIJ_SYNTHETIC_210", "Ask for website quote")
    leads = [
        _lead("ChIJ_SYNTHETIC_210", "Known Cafe", website=""),
        _lead("ChIJ_SYNTHETIC_211", "Fresh Cafe", website=""),
    ]
    merged = merge_local_state(leads, store)
    by_id = {item.lead.place_id: item for item in merged}
    assert by_id["ChIJ_SYNTHETIC_210"].previously_seen is True
    assert by_id["ChIJ_SYNTHETIC_210"].contact_status == "follow_up"
    assert by_id["ChIJ_SYNTHETIC_210"].notes == "Ask for website quote"
    assert by_id["ChIJ_SYNTHETIC_211"].previously_seen is False
    assert by_id["ChIJ_SYNTHETIC_211"].contact_status == "new"
    store.close()


def test_filter_logic(tmp_path: Path) -> None:
    item = merge_local_state(
        [_lead("ChIJ_SYNTHETIC_212", "Harbor Cafe", website="", phone="+54 11 0000")],
        LocalLeadStore(tmp_path / "filter.db"),
    )[0]
    item.contact_status = "contacted"
    assert matches_filters(item, text="harbor", min_score=10, no_website_only=True, has_phone=True)
    assert not matches_filters(item, text="pizzeria")
    assert not matches_filters(item, contact_status="won")
    assert matches_filters(item, contact_status="contacted")
    assert matches_filters(item, opportunity_level="high")
    assert not matches_filters(item, opportunity_level="low")
    assert matches_filters(item, presence="no_website")
    assert not matches_filters(item, presence="social_only")
    item.next_follow_up_at = "2020-01-01T00:00:00+00:00"
    item.contact_status = "contacted"
    assert matches_filters(item, follow_up_view="overdue")
    item.tags = "priority, call"
    assert matches_filters(item, tag="priority")
    assert not matches_filters(item, tag="email-later")


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def search_text(self, **kwargs: Any) -> TextSearchResult:
        self.calls += 1
        place = synthetic_place(f"ChIJ_SYNTHETIC_22{self.calls}", f"Cafe {self.calls}", website="")
        return TextSearchResult(places=[place], api_requests=1, pages_fetched=1)


def test_service_search_merges_local_state(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    store.set_contact_status("ChIJ_SYNTHETIC_221", "rejected")
    service = LeadService(store)
    config = SearchConfig(business="cafe", locations=["Example City"], country="AR", delay=0)
    report, managed = service.search(config, client=_FakeClient(), sleeper=lambda _: None)
    assert report.api_requests == 1
    assert managed[0].previously_seen is True
    assert managed[0].contact_status == "rejected"


def test_cancel_stops_further_queries(tmp_path: Path) -> None:
    cancelled = {"flag": False}

    class CancellingClient(_FakeClient):
        def search_text(self, **kwargs: Any) -> TextSearchResult:
            result = super().search_text(**kwargs)
            cancelled["flag"] = True
            return result

    client = CancellingClient()
    config = SearchConfig(
        business="cafe",
        locations=["Example City", "Other City"],
        country="AR",
        delay=0,
    )
    store = LocalLeadStore(tmp_path / "cancel.db")
    service = LeadService(store)
    report, managed = service.search(
        config,
        client=client,
        is_cancelled=lambda: cancelled["flag"],
        sleeper=lambda _: None,
    )
    assert client.calls == 1
    assert report.cancelled is True
    assert len(managed) == 1
