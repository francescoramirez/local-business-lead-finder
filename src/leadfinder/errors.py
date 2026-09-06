from __future__ import annotations

import re

_API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{10,}")
_BEARER_PATTERN = re.compile(r"(?i)(api[_-]?key|authorization|x-goog-api-key)\s*[:=]\s*\S+")


def redact_secrets(text: str) -> str:
    """Remove API keys and auth headers from text that may be logged or raised."""
    redacted = _API_KEY_PATTERN.sub("[REDACTED]", text)
    return _BEARER_PATTERN.sub(r"\1=[REDACTED]", redacted)


class LeadFinderError(Exception):
    """Base error for user-facing CLI failures."""

    def __init__(self, message: str) -> None:
        super().__init__(redact_secrets(message))


class MissingApiKeyError(LeadFinderError):
    pass


class ConfigError(LeadFinderError):
    pass


class PlacesAuthError(LeadFinderError):
    """Invalid or unauthorized credentials. Do not retry."""


class PlacesInvalidRequestError(LeadFinderError):
    """Permanent client/request error such as 400. Do not retry."""


class PlacesRateLimitError(LeadFinderError):
    """429 after retries were exhausted."""


class PlacesServerError(LeadFinderError):
    """5xx after retries were exhausted."""


class PlacesClientError(LeadFinderError):
    """Unexpected Places HTTP failure."""


class ExportError(LeadFinderError):
    pass
