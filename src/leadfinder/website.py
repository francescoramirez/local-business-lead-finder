from __future__ import annotations

from leadfinder.digital_presence import (
    AGGREGATOR_HOSTS,
    SOCIAL_HOSTS,
    PresenceAnalyzer,
    analyze_lead_website,
    classify_url,
)

__all__ = [
    "AGGREGATOR_HOSTS",
    "SOCIAL_HOSTS",
    "PresenceAnalyzer",
    "analyze_lead_website",
    "classify_url",
    "probe_url",
]


def probe_url(url: str, *, timeout: float = 5.0) -> str:
    """Reachability-aware classification used by older call sites."""
    del timeout
    return PresenceAnalyzer().analyze(url).category
