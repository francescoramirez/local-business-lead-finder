from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

from leadfinder.errors import (
    PlacesAuthError,
    PlacesClientError,
    PlacesInvalidRequestError,
    PlacesRateLimitError,
    PlacesServerError,
    redact_secrets,
)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
TRANSIENT_STATUS = {429, 500, 502, 503, 504}
AUTH_STATUS = {401, 403}
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 4
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0


@dataclass
class TextSearchResult:
    places: list[dict[str, Any]]
    api_requests: int
    pages_fetched: int


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        return max(0.0, retry_at.timestamp() - time.time())


class PlacesClient:
    """Google Places API (New) Text Search client."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key.strip():
            raise PlacesInvalidRequestError("Places API key is empty.")
        self._api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep
        self._opener = opener or urllib.request.urlopen

    def search_text(
        self,
        *,
        text_query: str,
        field_mask: str,
        page_size: int,
        max_pages: int,
        language_code: str,
        region_code: str,
        included_type: str = "",
        remaining_requests: int | None = None,
    ) -> TextSearchResult:
        payload: dict[str, Any] = {
            "textQuery": text_query,
            "languageCode": language_code,
            "regionCode": region_code,
            "pageSize": min(max(page_size, 1), 20),
        }
        if included_type:
            payload["includedType"] = included_type

        places: list[dict[str, Any]] = []
        api_requests = 0
        pages_fetched = 0
        budget = remaining_requests if remaining_requests is not None else max_pages

        for page_number in range(max_pages):
            if api_requests >= budget:
                break
            data = self._post(payload, field_mask)
            api_requests += 1
            pages_fetched += 1
            places.extend(data.get("places") or [])
            token = data.get("nextPageToken")
            if not token:
                break
            # Keep the original search parameters. Places Text Search (New)
            # only allows pageToken, pageSize, and maxResultCount to change.
            payload = dict(payload)
            payload["pageToken"] = token
            if page_number < max_pages - 1 and api_requests < budget:
                continue

        return TextSearchResult(
            places=places,
            api_requests=api_requests,
            pages_fetched=pages_fetched,
        )

    def _post(self, payload: dict[str, Any], field_mask: str) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            SEARCH_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": field_mask,
            },
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw)
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                last_error = self._map_http_error(error.code, detail)
                if error.code not in TRANSIENT_STATUS or attempt >= self.max_retries:
                    raise last_error from error
                self._sleep(self._backoff_delay(attempt, error.headers.get("Retry-After")))
            except urllib.error.URLError as error:
                last_error = PlacesClientError(
                    f"Network error talking to Places API: {error.reason}"
                )
                if attempt >= self.max_retries:
                    raise last_error from error
                self._sleep(self._backoff_delay(attempt, None))
        raise last_error or PlacesClientError("Places API request failed.")

    def _map_http_error(self, status: int, detail: str) -> Exception:
        message = redact_secrets(detail.strip() or f"HTTP {status}")
        if status in AUTH_STATUS:
            return PlacesAuthError(
                "Google rejected the Places API credentials. Check that the key is valid "
                f"and restricted to Places API (New). HTTP {status}."
            )
        if status == 400:
            return PlacesInvalidRequestError(
                f"Invalid Places Text Search request (HTTP 400): {message}"
            )
        if status == 429:
            return PlacesRateLimitError("Places API rate limit exceeded (HTTP 429).")
        if status >= 500:
            return PlacesServerError(f"Places API server error (HTTP {status}).")
        return PlacesClientError(f"Places API error (HTTP {status}): {message}")

    def _backoff_delay(self, attempt: int, retry_after: str | None) -> float:
        header_delay = _parse_retry_after(retry_after)
        if header_delay is not None:
            return min(header_delay, DEFAULT_MAX_DELAY)
        exp = min(DEFAULT_MAX_DELAY, DEFAULT_BASE_DELAY * (2**attempt))
        jitter = random.uniform(0, exp * 0.25)
        return exp + jitter
