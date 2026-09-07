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


def merge_imported_filters(
    existing: dict[str, dict[str, Any]], incoming: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    merged = dict(existing)
    for name, spec in incoming.items():
        key = name.strip()
        if not key or not isinstance(spec, dict):
            continue
        if key not in merged:
            merged[key] = spec
            continue
        imported = f"{key} (Imported)"
        n = 2
        while imported in merged:
            imported = f"{key} (Imported {n})"
            n += 1
        merged[imported] = spec
    return merged


def filters_for_workspace(custom: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"name": name, "filters": spec} for name, spec in custom.items()]


def filters_from_workspace(payload: object) -> dict[str, dict[str, Any]]:
    if isinstance(payload, dict) and "saved_filters" in payload:
        payload = payload.get("saved_filters")
    result: dict[str, dict[str, Any]] = {}
    if isinstance(payload, list):
        for item in payload:
            if (
                isinstance(item, dict)
                and item.get("name")
                and isinstance(item.get("filters"), dict)
            ):
                result[str(item["name"])] = item["filters"]
    elif isinstance(payload, dict):
        for name, spec in payload.items():
            if isinstance(spec, dict):
                result[str(name)] = spec
    return result
