"""Placeholder application icon (original, provisional — not a trademark)."""

from __future__ import annotations

from pathlib import Path

from leadfinder.desktop.runtime import resource_path

ICON_FILENAME = "leadfinder.ico"
ICON_PNG_FILENAME = "leadfinder.png"


def icon_path() -> Path:
    return Path(__file__).resolve().parent / ICON_FILENAME


def bundled_icon_path() -> Path:
    candidates = (
        Path(__file__).resolve().parent / ICON_FILENAME,
        resource_path("leadfinder", "desktop", "assets", ICON_FILENAME),
        resource_path("desktop", "assets", ICON_FILENAME),
    )
    for item in candidates:
        if item.is_file():
            return item
    return candidates[0]
