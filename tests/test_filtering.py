from __future__ import annotations

from leadfinder.filtering import apply_filters, is_contactable, is_operational, no_website
from leadfinder.normalize import place_to_lead
from tests.conftest import synthetic_place


def _lead(place_id: str = "ChIJ_SYNTHETIC_010", name: str = "Example Cafe", **kwargs):
    return place_to_lead(
        synthetic_place(place_id, name, **kwargs),
        source_query="cafe en Example City",
        location="Example City",
        search_term="cafe",
        business_preset="cafe",
        place_type="cafe",
        country="AR",
        region="Example",
    )


def test_operational_and_contactable_and_website_flags() -> None:
    open_lead = _lead(website="", phone="+54 11 1111 1111", status="OPERATIONAL")
    closed = _lead(website="https://example.test", phone="", status="CLOSED_PERMANENTLY")
    assert is_operational(open_lead)
    assert is_contactable(open_lead)
    assert no_website(open_lead)
    assert not is_operational(closed)
    assert not is_contactable(closed)


def test_default_filter_drops_permanently_closed() -> None:
    leads = [
        _lead(status="OPERATIONAL"),
        _lead(place_id="ChIJ_SYNTHETIC_011", name="Closed", status="CLOSED_PERMANENTLY"),
    ]
    filtered = apply_filters(leads)
    assert [lead.name for lead in filtered] == ["Example Cafe"]


def test_only_no_website_filter() -> None:
    leads = [
        _lead(website=""),
        _lead(place_id="ChIJ_SYNTHETIC_012", name="Has Web", website="https://example.test"),
    ]
    filtered = apply_filters(leads, only_no_website=True)
    assert [lead.name for lead in filtered] == ["Example Cafe"]
