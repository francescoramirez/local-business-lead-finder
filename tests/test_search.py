from __future__ import annotations

from typing import Any

from leadfinder.config import SearchConfig
from leadfinder.places_client import TextSearchResult
from leadfinder.search import run_search
from tests.conftest import synthetic_place


class FakeClient:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self.pages = pages
        self.calls: list[dict[str, Any]] = []

    def search_text(self, **kwargs: Any) -> TextSearchResult:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.pages) - 1)
        return TextSearchResult(places=self.pages[index], api_requests=1, pages_fetched=1)


def test_deduplicates_by_place_id() -> None:
    place = synthetic_place("ChIJ_SYNTHETIC_030", "Dup Cafe", website="")
    client = FakeClient([[place], [place]])
    config = SearchConfig(
        business="cafe",
        locations=["Example City", "Other City"],
        country="AR",
        region="Example",
        delay=0,
        max_requests=10,
    )
    report = run_search(config, client, sleeper=lambda _: None)  # type: ignore[arg-type]
    assert report.places_found == 2
    assert report.duplicates_discarded == 1
    assert len(report.leads) == 1
    assert report.leads[0].place_id == "ChIJ_SYNTHETIC_030"


def test_max_requests_stops_further_queries() -> None:
    client = FakeClient(
        [
            [synthetic_place("ChIJ_SYNTHETIC_031", "One", website="")],
            [synthetic_place("ChIJ_SYNTHETIC_032", "Two", website="")],
        ]
    )
    config = SearchConfig(
        business="cafe",
        locations=["Example City", "Other City"],
        country="US",
        delay=0,
        max_requests=1,
    )
    report = run_search(config, client, sleeper=lambda _: None)  # type: ignore[arg-type]
    assert report.api_requests == 1
    assert report.queries_executed == 1
    assert len(client.calls) == 1


def test_identical_in_run_query_is_a_permitted_cache_hit() -> None:
    place = synthetic_place("ChIJ_SYNTHETIC_033", "Cache Cafe", website="")
    client = FakeClient([[place]])

    class DuplicateLocationConfig(SearchConfig):
        def resolved_locations(self) -> list[str]:
            return ["Example City", "Example City"]

    config = DuplicateLocationConfig(
        business="cafe",
        locations=["Example City"],
        country="AR",
        delay=0,
    )
    report = run_search(config, client, sleeper=lambda _: None)  # type: ignore[arg-type]
    assert report.api_requests == 1
    assert report.cache_hits == 1
    assert len(client.calls) == 1


def test_website_analysis_runs_after_places_and_can_cancel() -> None:
    client = FakeClient([[synthetic_place("ChIJ_SYNTHETIC_034", "Analyzed", website="https://x.test")]])
    seen: list[str] = []

    def analyze(lead):
        seen.append(lead.place_id)
        lead.website_status = "has_website"
        return lead

    config = SearchConfig(
        business="cafe",
        locations=["Example City"],
        country="AR",
        delay=0,
        analyze_websites=True,
    )
    report = run_search(config, client, analyze=analyze, sleeper=lambda _: None)  # type: ignore[arg-type]
    assert seen == ["ChIJ_SYNTHETIC_034"]
    assert report.leads[0].website_status == "has_website"

