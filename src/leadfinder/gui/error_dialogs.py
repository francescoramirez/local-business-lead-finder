"""User-facing Qt error helpers. No raw tracebacks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from leadfinder.desktop.diagnostics import collect_diagnostics
from leadfinder.paths import log_dir

if TYPE_CHECKING:
    from pathlib import Path


def _open_logs() -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir())))


def _copy_diagnostics(db_path: Path | None = None) -> None:
    text = collect_diagnostics(db_path=db_path)
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def show_info(parent: QWidget | None, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def show_error(
    parent: QWidget | None,
    message: str,
    *,
    title: str = "LeadFinder",
    db_path: Path | None = None,
) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(message)
    box.setInformativeText("Technical details were written to the local log.")
    logs_btn = box.addButton("Open logs", QMessageBox.ButtonRole.ActionRole)
    copy_btn = box.addButton("Copy diagnostics", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Close", QMessageBox.ButtonRole.AcceptRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked is logs_btn:
        _open_logs()
    elif clicked is copy_btn:
        _copy_diagnostics(db_path)
