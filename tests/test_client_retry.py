from __future__ import annotations

import io
from email.message import EmailMessage
from typing import Any
from urllib.error import HTTPError

import pytest

from leadfinder.errors import PlacesAuthError, PlacesInvalidRequestError, PlacesRateLimitError
from leadfinder.places_client import PlacesClient
from tests.http import FakeResponse


def _http_error(status: int, body: str = "{}", retry_after: str | None = None) -> HTTPError:
    headers = EmailMessage()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError(
        "https://places.googleapis.com/v1/places:searchText",
        status,
        "error",
        headers,
        io.BytesIO(body.encode("utf-8")),
    )


def test_retries_429_and_respects_retry_after() -> None:
    sleeps: list[float] = []
    calls = {"count": 0}

    def opener(request: Any, timeout: float = 0) -> FakeResponse:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _http_error(429, retry_after="2")
        return FakeResponse({"places": [{"id": "ChIJ_SYNTHETIC_001"}]})

    client = PlacesClient("test-key", opener=opener, sleep=sleeps.append, max_retries=3)
    result = client.search_text(
        text_query="cafe en Example City, Exampleland",
        field_mask="places.id,nextPageToken",
        page_size=5,
        max_pages=1,
        language_code="en",
        region_code="US",
    )
    assert result.places[0]["id"] == "ChIJ_SYNTHETIC_001"
    assert sleeps == [2.0]
    assert result.api_requests == 1
    assert result.http_attempts == 2


def test_retries_server_errors() -> None:
    calls = {"count": 0}

    def opener(request: Any, timeout: float = 0) -> FakeResponse:
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
    assert result.api_requests == 1
    assert result.http_attempts == 3
    assert calls["count"] == 3


def test_does_not_retry_invalid_request() -> None:
    def opener(request: Any, timeout: float = 0) -> FakeResponse:
        raise _http_error(400, '{"error":{"message":"bad"}}')

    client = PlacesClient("test-key", opener=opener, sleep=lambda _: None)
    with pytest.raises(PlacesInvalidRequestError):
        client.search_text(
            text_query="x",
            field_mask="places.id",
            page_size=1,
            max_pages=1,
            language_code="en",
            region_code="US",
        )


def test_does_not_retry_auth_errors_or_leak_key() -> None:
    def opener(request: Any, timeout: float = 0) -> FakeResponse:
        raise _http_error(403, '{"error":{"message":"AIzaSyA-not-a-real-key-value"}}')

    client = PlacesClient("AIzaSyA-not-a-real-key-value", opener=opener, sleep=lambda _: None)
    with pytest.raises(PlacesAuthError) as error:
        client.search_text(
            text_query="x",
            field_mask="places.id",
            page_size=1,
            max_pages=1,
            language_code="en",
            region_code="US",
        )
    assert "AIza" not in str(error.value)


def test_exhausted_rate_limit_raises() -> None:
    def opener(request: Any, timeout: float = 0) -> FakeResponse:
        raise _http_error(429)

    client = PlacesClient("test-key", opener=opener, sleep=lambda _: None, max_retries=1)
    with pytest.raises(PlacesRateLimitError):
        client.search_text(
            text_query="x",
            field_mask="places.id",
            page_size=1,
            max_pages=1,
            language_code="en",
            region_code="US",
        )
