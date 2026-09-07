from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from leadfinder.application.service import LeadService  # noqa: E402
from leadfinder.desktop.settings_keys import DEFAULT_PAGES  # noqa: E402
from leadfinder.gui.about_dialog import AboutDialog  # noqa: E402
from leadfinder.gui.main_window import MainWindow  # noqa: E402
from leadfinder.gui.settings_dialog import SettingsDialog  # noqa: E402
from leadfinder.storage.local_leads import LocalLeadStore  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_settings_save_defaults(qapp, tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    window = MainWindow(LeadService(LocalLeadStore(tmp_path / "w.db")), settings=settings)
    dialog = SettingsDialog(settings, window)
    dialog.default_country.setText("uy")
    dialog.default_region.setText("Montevideo")
    dialog.default_pages.setValue(2)
    dialog.default_fields.setCurrentText("pro")
    dialog._save()
    settings.sync()
    assert settings.value("country") == "UY"
    assert settings.value("region") == "Montevideo"
    assert int(settings.value(DEFAULT_PAGES)) == 2
    assert settings.value("fields") == "pro"
    ini = tmp_path / "s.ini"
    if ini.exists():
        raw = ini.read_text(encoding="utf-8")
        assert "AIza" not in raw
        assert "gsk_" not in raw
    window.close()


def test_invalid_settings_recovery(qapp, tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    settings.setValue("pages", "not-a-number")
    settings.setValue("fields", "not-a-profile")
    window = MainWindow(LeadService(LocalLeadStore(tmp_path / "w.db")), settings=settings)
    assert window.pages.value() >= 1
    window.close()


def test_about_uses_package_version(qapp, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QLabel

    from leadfinder import __version__

    window = MainWindow(LeadService(LocalLeadStore(tmp_path / "w.db")))
    about = AboutDialog(window)
    texts = [widget.text() for widget in about.findChildren(QLabel) if widget.text()]
    assert any(__version__ in text for text in texts)
    window.close()
