from __future__ import annotations

import json
from pathlib import Path

import pytest

from leadfinder.errors import ExportError
from leadfinder.exporters import export_leads, write_csv, write_json
from leadfinder.models import EXPORT_COLUMNS
from leadfinder.normalize import place_to_lead
from leadfinder.scoring import score_lead
from tests.conftest import synthetic_place


def _lead():
    return score_lead(
        place_to_lead(
            synthetic_place("ChIJ_SYNTHETIC_040", "Export Cafe", website=""),
            source_query="cafe en Example City",
            location="Example City",
            search_term="cafe",
            business_preset="cafe",
            place_type="cafe",
            country="AR",
            region="Example",
            fetched_at="2026-01-01T00:00:00+00:00",
        )
    )


def test_csv_and_json_use_stable_columns(tmp_path: Path) -> None:
    lead = _lead()
    csv_path = write_csv([lead], tmp_path / "leads.csv", force=True)
    json_path = write_json([lead], tmp_path / "leads.json", force=True)
    header = csv_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == list(EXPORT_COLUMNS)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert list(payload[0]) == list(EXPORT_COLUMNS)
    assert payload[0]["place_id"] == "ChIJ_SYNTHETIC_040"
    assert payload[0]["data_source"] == "Google Maps"


def test_export_refuses_silent_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "leads.csv"
    write_csv([_lead()], path, force=True)
    with pytest.raises(ExportError):
        write_csv([_lead()], path, force=False)


def test_both_formats_share_timestamped_stem(tmp_path: Path) -> None:
    paths = export_leads(
        [_lead()],
        output=tmp_path / "batch",
        formats=("csv", "json"),
        stamp="20260101T000000",
        force=True,
    )
    assert [path.suffix for path in paths] == [".csv", ".json"]
