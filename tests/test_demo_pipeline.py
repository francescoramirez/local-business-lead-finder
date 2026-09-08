from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from leadfinder.application.service import LeadService  # noqa: E402
from leadfinder.demo import STATUSES, seed_demo_database  # noqa: E402
from leadfinder.gui.main_window import MainWindow  # noqa: E402
from leadfinder.storage.local_leads import LocalLeadStore  # noqa: E402
from leadfinder.workflow import CONTACT_STATUSES, PIPELINE_COLUMNS  # noqa: E402

DEMO_COUNT = 80


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _status_counts(store: LocalLeadStore) -> Counter[str]:
    return Counter(row.contact_status for row in store.list_all())


def _pipeline_board_count(window: MainWindow) -> int:
    return sum(column.count() for column in window.pipeline_page.columns.values())


def _column_count(window: MainWindow, status: str) -> int:
    return window.pipeline_page.columns[status].count()


def _patch_workspace(
    monkeypatch: pytest.MonkeyPatch, data: Path, user_db: Path, demo_db: Path
) -> None:
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


def test_demo_seed_status_counts_match_pipeline_columns(tmp_path: Path) -> None:
    path = seed_demo_database(tmp_path / "leadfinder-demo.db", count=DEMO_COUNT)
    store = LocalLeadStore(path)
    counts = _status_counts(store)
    expected = Counter(STATUSES[index % len(STATUSES)] for index in range(DEMO_COUNT))
    assert len(store.list_all()) == DEMO_COUNT
    assert counts == expected
    assert counts["do_not_contact"] == 0
    for status in CONTACT_STATUSES:
        counts[status]
    board = sum(counts[status] for status in PIPELINE_COLUMNS)
    assert board == DEMO_COUNT - counts["rejected"] - counts["do_not_contact"]
    assert board > 0
    store.close()


def test_demo_switch_fills_pipeline_from_active_store(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    user_db = data / "leadfinder.db"
    demo_db = data / "leadfinder-demo.db"
    _patch_workspace(monkeypatch, data, user_db, demo_db)
    seed_demo_database(demo_db, count=DEMO_COUNT)

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    LocalLeadStore(user_db).close()
    window = MainWindow(LeadService(LocalLeadStore(user_db)), settings=settings)
    assert window._is_demo_workspace() is False
    assert window.prospects_page.table.rowCount() == 0
    assert _pipeline_board_count(window) == 0
    assert window.model.leads() == []

    window.enter_demo_mode()
    demo_store = window.service.store
    persisted = _status_counts(demo_store)
    assert window.prospects_page.table.rowCount() == DEMO_COUNT
    assert _pipeline_board_count(window) > 0
    for status in PIPELINE_COLUMNS:
        assert _column_count(window, status) == persisted[status]
    assert persisted["rejected"] > 0
    user_check = LocalLeadStore(user_db)
    assert user_check.list_all() == []
    user_check.close()

    window.exit_demo_mode()
    assert window._is_demo_workspace() is False
    assert window.prospects_page.table.rowCount() == 0
    assert _pipeline_board_count(window) == 0
    empty = LocalLeadStore(user_db)
    assert empty.list_all() == []
    empty.close()

    window.enter_demo_mode()
    persisted = _status_counts(window.service.store)
    assert window.prospects_page.table.rowCount() == DEMO_COUNT
    assert _pipeline_board_count(window) > 0
    for status in PIPELINE_COLUMNS:
        assert _column_count(window, status) == persisted[status]
    window.close()


def test_demo_status_change_moves_pipeline_and_isolates_user_db(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    user_db = data / "leadfinder.db"
    demo_db = data / "leadfinder-demo.db"
    _patch_workspace(monkeypatch, data, user_db, demo_db)
    seed_demo_database(demo_db, count=DEMO_COUNT)

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    LocalLeadStore(user_db).close()
    window = MainWindow(LeadService(LocalLeadStore(user_db)), settings=settings)
    window.enter_demo_mode()

    new_id = "ChIJ_DEMO_0000"
    assert window.service.store.get(new_id).contact_status == "new"
    before_new = _column_count(window, "new")
    before_contacted = _column_count(window, "contacted")

    window._select_place(new_id)
    assert window._selected is not None
    assert window._selected.lead.place_id == new_id
    assert window.tabs.currentIndex() == 0

    updated = window.service.set_status(window._selected, "contacted")
    window._selected = updated
    window.model.update_row(updated)
    window._refresh_secondary()

    assert window.service.store.get(new_id).contact_status == "contacted"
    assert _column_count(window, "new") == before_new - 1
    assert _column_count(window, "contacted") == before_contacted + 1
    user_check = LocalLeadStore(user_db)
    assert user_check.list_all() == []
    user_check.close()

    window.undo_last()
    assert window.service.store.get(new_id).contact_status == "new"
    assert _column_count(window, "new") == before_new
    assert _column_count(window, "contacted") == before_contacted
    history = window.service.activities(new_id)
    assert any(activity.reverses_activity_id for activity in history)
    window.close()
