from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from leadfinder.application.service import LeadService  # noqa: E402
from leadfinder.errors import (  # noqa: E402
    AIAuthError,
    AIResponseValidationError,
    AITimeoutError,
)
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
    assert window.tabs.count() == 5
    assert window.tabs.tabText(4) == "Learn"
    assert window.learn_tabs.tabText(0) == "Analytics"
    assert window.learn_tabs.tabText(1) == "Insights"
    assert window.learn_tabs.tabText(2) == "Experiments"
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


class _FakePrep:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error
        from leadfinder.ai.models import SalesPrepResult

        self.result = result or SalesPrepResult(
            opportunity_summary="Strong local activity with 238 reviews.",
            pitch_angle="Complement Instagram with a simple site.",
            value_props=["Direct inquiries"],
            opening_message="Hola, vi su presencia en Instagram.",
            talking_points=["Own the web presence"],
            objections=["Instagram is enough"],
            cautions=["Do not promise rankings"],
            next_step="Review and contact manually.",
            observed=["Social-only presence", "238 reviews"],
        )

    def generate_sales_prep(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def _wait_prep(window, qapp) -> None:
    worker = window._prep_worker
    assert worker is not None
    assert worker.wait(5000)
    qapp.processEvents()


def test_sales_prep_is_manual_copy_save_and_errors(qapp, tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    fake = _FakePrep()
    service = LeadService(store, ai_provider=fake)
    window = MainWindow(service)
    item = _managed(store, "ChIJ_SYNTHETIC_401", "Cafe Example")
    item.lead.website_status = "social_only"
    item.lead.rating = 4.6
    item.lead.user_rating_count = 238
    window.model.set_leads([item])
    window._update_empty_state()
    window.table.selectRow(0)
    window._show_lead(item)
    window.detail_tabs.setCurrentIndex(1)
    assert window.detail_tabs.tabText(1) == "Sales Prep"
    assert fake.calls == 0
    assert window.sales_prep.generate_count == 0
    assert window.sales_prep.summary.toPlainText() == ""

    window.sales_prep.generate_btn.click()
    _wait_prep(window, qapp)
    assert fake.calls == 1
    assert "238" in window.sales_prep.summary.toPlainText()
    assert "Suggested draft" not in window.sales_prep.opener.toPlainText()
    assert window.sales_prep.opener.toPlainText().startswith("Hola")

    window._copy_opener()
    clipboard = qapp.clipboard()
    assert clipboard is not None
    assert clipboard.text() == window.sales_prep.opener.toPlainText()

    window.sales_prep.regenerate_btn.click()
    _wait_prep(window, qapp)
    assert fake.calls == 2
    assert window.sales_prep.generate_count == 2

    window.sales_prep.save_notes_btn.click()
    assert "AI sales prep" in window.notes.toPlainText()
    assert "Sales prep saved" in window.detail_activity.toPlainText()

    window.service.ai_provider = _FakePrep(error=AITimeoutError("AI provider timed out."))
    window.start_sales_prep()
    _wait_prep(window, qapp)
    assert "timed out" in window.sales_prep.busy.text().lower()

    window.service.ai_provider = _FakePrep(error=AIAuthError("AI API key invalid."))
    window.start_sales_prep()
    _wait_prep(window, qapp)
    assert "invalid" in window.sales_prep.busy.text().lower()

    window.service.ai_provider = _FakePrep(
        error=AIResponseValidationError("AI returned an invalid structured response.")
    )
    window.start_sales_prep()
    _wait_prep(window, qapp)
    assert "invalid structured" in window.sales_prep.busy.text().lower()

    window.close()
    restored = LocalLeadStore(tmp_path / "leads.db")
    state = restored.get("ChIJ_SYNTHETIC_401")
    assert state is not None
    assert "AI sales prep" in state.notes
    for key in window.settings.allKeys():
        value = str(window.settings.value(key))
        assert "GROQ_API_KEY" not in key
        assert "gsk_" not in value.lower()
    restored.close()


def test_analytics_tab_empty_and_populated(qapp, tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "an.db")
    service = LeadService(store)
    window = MainWindow(service)
    assert window.tabs.tabText(4) == "Learn"
    window._refresh_analytics()
    assert "Not enough history" in window.analytics_page.empty.text()
    campaign = service.create_campaign(
        name="Cafes Example", business_preset="cafe", location="Example"
    )
    item = _managed(store, "ChIJ_SYNTHETIC_601", "Cafe Example")
    store.mark_seen(
        item.lead.place_id,
        business_preset="cafe",
        source_location="Example",
        website_status="social_only",
        campaign_id=campaign.id,
    )
    store.attach_leads(campaign.id, [item.lead.place_id])
    store.set_contact_status(item.lead.place_id, "contacted")
    window.analytics_page.period.setCurrentIndex(window.analytics_page.period.findData(0))
    window._refresh_campaigns()
    window._refresh_analytics()
    assert "Contacted" in window.analytics_page.headline.text()
    assert window.campaign.findText("Auto (same-day search)") >= 0
    window.insights_page.period.setCurrentIndex(window.insights_page.period.findData(0))
    window._refresh_insights()
    assert "contact" in window.insights_page.baseline.text().lower()
    window.close()


