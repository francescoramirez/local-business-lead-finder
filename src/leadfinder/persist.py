from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PlaceIdStore:
    """Permanent store limited to Place IDs, which Google allows persisting."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.ids: set[str] = set()
        if path and path.exists() and path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.ids = {str(item) for item in data.get("place_ids", []) if item}

    def add(self, place_id: str) -> None:
        if place_id:
            self.ids.add(place_id)

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "place_ids": sorted(self.ids),
            "note": "Only Place IDs are persisted. Full Places responses are not stored.",
        }
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.path)
