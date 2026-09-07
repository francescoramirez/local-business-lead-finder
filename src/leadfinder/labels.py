"""Shared display labels. One source for GUI, analytics, and AI."""

from __future__ import annotations

PRESENCE_LABELS = {
    "no_website": "No website",
    "social_only": "Social only",
    "link_aggregator": "Link aggregator",
    "weak_website": "Weak website",
    "has_website": "Website",
    "unreachable": "Unreachable",
    "non_https": "HTTP only",
    "parked": "Parked",
    "unknown": "Unknown",
    "": "Unknown",
}

OPPORTUNITY_LABELS = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "": "Unknown",
}

MANUAL_PRIORITIES: tuple[str, ...] = ("high", "normal", "low", "ignore")

MANUAL_PRIORITY_LABELS = {
    "high": "High",
    "normal": "Normal",
    "low": "Low",
    "ignore": "Ignore",
}
