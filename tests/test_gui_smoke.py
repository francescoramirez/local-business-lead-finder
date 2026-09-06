from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from leadfinder.application.service import LeadService  # noqa: E402
from leadfinder.gui.main_window import MainWindow  # noqa: E402
from leadfinder.normalize import place_to_lead  # noqa: E402
from leadfinder.scoring import score_lead  # noqa: E402
from leadfinder.storage.local_leads import LocalLeadStore  # noqa: E402
from tests.conftest import synthetic_place  # noqa: E402


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _managed(store: LocalLeadStore, place_id: str, name: str):
    from leadfinder.application.service import merge_local_state

    lead = score_lead(
        place_to_lead(
            synthetic_place(place_id, name, website=""),
            source_query="cafe en Example City",
            location="Example City",
            search_term="cafe",
            business_preset="cafe",
            place_type="cafe",
            country="AR",
            region="Example",
        )
    )
    return merge_local_state([lead], store)[0]


def test_main_window_loads_presets_and_dry_run(qapp, tmp_path: Path) -> None:
    window = MainWindow(LeadService(LocalLeadStore(tmp_path / "leads.db")))
    assert window.preset.count() >= 10
    window.location.setText("Mar del Plata")
    window.region.setText("Buenos Aires")
    window.country.setText("AR")
    cafe_index = window.preset.findData("cafe")
    window.preset.setCurrentIndex(cafe_index)
    window.run_dry_run()
    text = window.summary.toPlainText()
    assert "Text Search Enterprise" in text
    assert "Mar del Plata" in text
    assert "No API requests were made." in text
    window.close()


def test_table_selection_and_status_persist(qapp, tmp_path: Path) -> None:
    db = tmp_path / "leads.db"
    store = LocalLeadStore(db)
    service = LeadService(store)
    window = MainWindow(service)
    item = _managed(store, "ChIJ_SYNTHETIC_301", "Harbor Cafe")
    window.model.set_leads([item])
    window._update_empty_state()
    window.table.selectRow(0)
    window._show_lead(item)
    assert "Harbor Cafe" in window.detail_name.text()
    contacted = window.contact_status.findData("contacted")
    window.contact_status.setCurrentIndex(contacted)
    window._on_status_changed()
    window.close()

    restored = LocalLeadStore(db).get("ChIJ_SYNTHETIC_301")
    assert restored is not None
    assert restored.contact_status == "contacted"


def test_export_uses_core_exporter(qapp, tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    service = LeadService(store)
    window = MainWindow(service)
    window.model.set_leads([_managed(store, "ChIJ_SYNTHETIC_302", "Export Cafe")])
    path = service.export([window.model.lead_at(0).lead], fmt="csv", output=tmp_path / "out.csv")
    assert path.exists()
    assert "Export Cafe" in path.read_text(encoding="utf-8")
    window.close()


def test_opportunity_filter_and_presence_details(qapp, tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    service = LeadService(store)
    window = MainWindow(service)
    hot = _managed(store, "ChIJ_SYNTHETIC_303", "Hot Cafe")
    cold_lead = score_lead(
        place_to_lead(
            synthetic_place(
                "ChIJ_SYNTHETIC_304",
                "Cold Cafe",
                website="https://cold.test",
            ),
            source_query="cafe en Example City",
            location="Example City",
            search_term="cafe",
            business_preset="cafe",
            place_type="cafe",
            country="AR",
            region="Example",
        )
    )
    from leadfinder.application.service import merge_local_state

    cold = merge_local_state([cold_lead], store)[0]
    window.model.set_leads([hot, cold])
    window._update_empty_state()
    window.filter_opportunity.setCurrentIndex(window.filter_opportunity.findData("high"))
    window._apply_filters()
    assert window.proxy.rowCount() == 1
    window.table.selectRow(0)
    window._show_lead(hot)
    assert "Digital presence" in window.detail_presence.text()
    assert "High" in window.detail_score.text()
    window.notes.setPlainText("Call Tuesday")
    window._save_notes()
    window.close()
    restored = LocalLeadStore(tmp_path / "leads.db").get("ChIJ_SYNTHETIC_303")
    assert restored is not None
    assert restored.notes == "Call Tuesday"


def test_pipeline_dashboard_and_follow_up_flow(qapp, tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    service = LeadService(store)
    window = MainWindow(service)
    assert window.tabs.count() == 4
    item = _managed(store, "ChIJ_SYNTHETIC_305", "Pipeline Cafe")
    window.model.set_leads([item])
    updated = window.service.set_status(item, "contacted")
    window.model.update_row(updated)
    window._show_lead(updated)
    assert "Status changed" in window.detail_activity.toPlainText()
    updated = window.service.set_follow_up(updated, "2020-01-01T00:00:00+00:00")
    window.model.set_leads([updated])
    window.filter_follow.setCurrentIndex(window.filter_follow.findData("overdue"))
    window._apply_filters()
    assert window.proxy.rowCount() == 1
    window.service.set_tags(updated, "priority")
    window._refresh_secondary()
    assert window.pipeline_page.columns["contacted"].count() == 1
    assert "overdue" in window.dashboard_page.overdue_banner.text().lower()
    path = window.service.export_pipeline([updated], tmp_path / "pipeline.csv")
    text = path.read_text(encoding="utf-8")
    assert "contact_status" in text
    assert "next_follow_up_at" in text
    window.close()
    restored = LocalLeadStore(tmp_path / "leads.db")
    state = restored.get("ChIJ_SYNTHETIC_305")
    assert state is not None
    assert state.contact_status == "contacted"
    assert state.tags == "priority"
    restored.close()
