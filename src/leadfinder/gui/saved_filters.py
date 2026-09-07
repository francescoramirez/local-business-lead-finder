"""Named filter presets stored in QSettings (configuration only, not result sets)."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QSettings

BUILTIN_FILTERS: dict[str, dict[str, Any]] = {
    "High opportunity": {
        "text": "",
        "min_score": 0,
        "no_website": False,
        "has_phone": False,
        "operational": True,
        "status": "",
        "opportunity": "high",
        "presence": "",
        "follow": "",
        "tag": "",
        "priority": "",
    },
    "New": {
        "text": "",
        "min_score": 0,
        "no_website": False,
        "has_phone": False,
        "operational": True,
        "status": "new",
        "opportunity": "",
        "presence": "",
        "follow": "",
        "tag": "",
        "priority": "",
    },
    "Has phone": {
        "text": "",
        "min_score": 0,
        "no_website": False,
        "has_phone": True,
        "operational": True,
        "status": "",
        "opportunity": "",
        "presence": "",
        "follow": "",
        "tag": "",
        "priority": "",
    },
    "No website/social": {
        "text": "",
        "min_score": 0,
        "no_website": True,
        "has_phone": False,
        "operational": True,
        "status": "",
        "opportunity": "",
        "presence": "no_website",
        "follow": "",
        "tag": "",
        "priority": "",
    },
}

SETTINGS_KEY = "saved_filters"


def load_custom_filters(settings: QSettings) -> dict[str, dict[str, Any]]:
    raw = str(settings.value(SETTINGS_KEY, "") or "")
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, dict[str, Any]] = {}
    for name, spec in payload.items():
        if isinstance(name, str) and isinstance(spec, dict) and name.strip():
            cleaned[name.strip()] = spec
    return cleaned


def store_custom_filters(settings: QSettings, custom: dict[str, dict[str, Any]]) -> None:
    settings.setValue(SETTINGS_KEY, json.dumps(custom, ensure_ascii=False))


def all_named_filters(settings: QSettings) -> dict[str, dict[str, Any]]:
    merged = dict(BUILTIN_FILTERS)
    merged.update(load_custom_filters(settings))
    return merged
