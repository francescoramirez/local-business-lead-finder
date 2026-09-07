from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from leadfinder.desktop.settings_keys import ONBOARDING_COMPLETED, PLACES_COST_NOTICE  # noqa: E402
from leadfinder.gui.onboarding import (  # noqa: E402
    OnboardingDialog,
    mark_onboarding_completed,
    onboarding_completed,
)


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _ini(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)


def test_first_run_incomplete(tmp_path: Path) -> None:
    settings = _ini(tmp_path)
    assert onboarding_completed(settings) is False


def test_completed_skips_and_restart(tmp_path: Path) -> None:
    settings = _ini(tmp_path)
    mark_onboarding_completed(settings)
    assert onboarding_completed(settings) is True
    settings.setValue(ONBOARDING_COMPLETED, False)
    assert onboarding_completed(settings) is False


def test_configure_later_and_try_demo(qapp, tmp_path: Path) -> None:
    dialog = OnboardingDialog()
    dialog.stack.setCurrentIndex(dialog.stack.count() - 1)
    dialog.demo_check.setChecked(True)
    dialog._next()
    assert dialog.choice == "demo"
    dialog2 = OnboardingDialog()
    dialog2.stack.setCurrentIndex(dialog2.stack.count() - 1)
    dialog2.demo_check.setChecked(False)
    dialog2._next()
    assert dialog2.choice == "workspace"
    dialog.close()
    dialog2.close()


def test_cost_notice_key_is_qsettings_only(tmp_path: Path) -> None:
    settings = _ini(tmp_path)
    assert settings.value(PLACES_COST_NOTICE, False, type=bool) is False
    settings.setValue(PLACES_COST_NOTICE, True)
    settings.sync()
    assert "AIza" not in (tmp_path / "s.ini").read_text(encoding="utf-8")
