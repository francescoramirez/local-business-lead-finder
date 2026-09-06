from __future__ import annotations

import json
from pathlib import Path

from leadfinder.persist import PlaceIdStore


def test_place_id_store_persists_only_ids(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    store = PlaceIdStore(path)
    store.add("ChIJ_SYNTHETIC_050")
    store.add("")
    store.save()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["place_ids"] == ["ChIJ_SYNTHETIC_050"]
    assert "places" not in payload
    loaded = PlaceIdStore(path)
    assert loaded.ids == {"ChIJ_SYNTHETIC_050"}
