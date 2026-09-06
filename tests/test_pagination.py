from __future__ import annotations

import json
from typing import Any

from leadfinder.places_client import PlacesClient
from tests.http import FakeResponse


def test_pagination_keeps_original_search_parameters() -> None:
    captured: list[dict[str, Any]] = []
    pages = [
        {
            "places": [{"id": "ChIJ_SYNTHETIC_001", "displayName": {"text": "One"}}],
            "nextPageToken": "token-abc",
        },
        {
            "places": [{"id": "ChIJ_SYNTHETIC_002", "displayName": {"text": "Two"}}],
        },
    ]

    def opener(request: Any, timeout: float = 0) -> FakeResponse:
        captured.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse(pages[len(captured) - 1])

    client = PlacesClient("test-key", opener=opener, sleep=lambda _: None)
    result = client.search_text(
        text_query="cafe en Cordoba, Cordoba, Argentina",
        field_mask="places.id,nextPageToken",
        page_size=20,
        max_pages=3,
        language_code="es-419",
        region_code="AR",
        included_type="cafe",
    )

    assert result.api_requests == 2
    assert [place["id"] for place in result.places] == [
        "ChIJ_SYNTHETIC_001",
        "ChIJ_SYNTHETIC_002",
    ]
    assert captured[0] == {
        "textQuery": "cafe en Cordoba, Cordoba, Argentina",
        "languageCode": "es-419",
        "regionCode": "AR",
        "pageSize": 20,
        "includedType": "cafe",
    }
    assert captured[1]["pageToken"] == "token-abc"
    assert captured[1]["textQuery"] == captured[0]["textQuery"]
    assert captured[1]["includedType"] == "cafe"
    assert captured[1]["languageCode"] == "es-419"
    assert captured[1]["regionCode"] == "AR"
    assert captured[1]["pageSize"] == 20
