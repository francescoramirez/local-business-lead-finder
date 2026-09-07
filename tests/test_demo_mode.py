from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from leadfinder.application.service import LeadService  # noqa: E402
from leadfinder.demo import DEMO_NAMES, seed_demo_database  # noqa: E402
from leadfinder.gui.main_window import MainWindow  # noqa: E402
from leadfinder.storage.local_leads import LocalLeadStore  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


REAL_BRANDS = ("Starbucks", "McDonald", "Google", "Mercado Libre", "Globant")


def test_demo_dataset_is_synthetic_and_isolated(tmp_path: Path) -> None:
    user = tmp_path / "leadfinder.db"
    LocalLeadStore(user).close()
    demo = seed_demo_database(tmp_path / "leadfinder-demo.db")
    store = LocalLeadStore(demo)
    rows = store.list_all()
    assert 60 <= len(rows) <= 100
    labels = " ".join(item.label for item in rows)
    for brand in REAL_BRANDS:
        assert brand.lower() not in labels.lower()
    for name in DEMO_NAMES:
        assert name in labels
    store.close()
    user_store = LocalLeadStore(user)
    assert user_store.list_all() == []
    user_store.close()


def test_demo_mode_switch_reset_exit(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    user_db = data / "leadfinder.db"
    demo_db = data / "leadfinder-demo.db"
    monkeypatch.setattr("leadfinder.paths.data_dir", lambda: data)
    monkeypatch.setattr("leadfinder.paths.demo_db_path", lambda: demo_db)
    monkeypatch.setattr("leadfinder.demo.demo_db_path", lambda: demo_db)
    monkeypatch.setattr("leadfinder.demo.default_db_path", lambda: user_db)
    monkeypatch.setattr(
        "leadfinder.paths.is_user_database",
        lambda path: path.resolve() == user_db.resolve(),
    )

    monkeypatch.setattr(
        "leadfinder.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    user_store = LocalLeadStore(user_db)
    user_store.mark_seen("ChIJ_REAL_KEEP", label="Keep Me")
    user_store.close()
    window = MainWindow(LeadService(LocalLeadStore(user_db)), settings=settings)
    assert window._is_demo_workspace() is False
    window.enter_demo_mode()
    assert window._is_demo_workspace() is True
    assert not window.demo_banner.isHidden()
    assert "DEMO" in window.windowTitle()
    demo_count = len(window.service.store.list_all())
    assert demo_count >= 60
    window.reset_demo_data()
    assert window._is_demo_workspace() is True
    assert len(window.service.store.list_all()) == demo_count
    window.exit_demo_mode()
    assert window._is_demo_workspace() is False
    kept = LocalLeadStore(user_db)
    assert kept.get("ChIJ_REAL_KEEP") is not None
    kept.close()
    window.close()


def test_demo_analytics_available(tmp_path: Path) -> None:
    path = seed_demo_database(tmp_path / "demo.db")
    service = LeadService(LocalLeadStore(path))
    report = service.analytics_report(service.analytics_period(days=None))
    assert report.snapshot.total_leads >= 60
    text = service.campaign_cost_text(None, report)
    assert "Estimated list cost" in text or "Unknown" in text
    insights = service.insights_report(service.analytics_period(days=None))
    assert insights.ranked is not None
    service.store.close()
