"""Startup failure dialog. Never auto-deletes the database."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from leadfinder.paths import data_dir

OPEN_DATA = "Open data folder"
OPEN_DEMO = "Open demo"
RESTORE = "Restore backup"
EXIT = "Exit"

CHOICE_EXIT = "exit"
CHOICE_DEMO = "demo"
CHOICE_RESTORE = "restore"
CHOICE_FOLDER = "folder"


def show_startup_failure(parent: QWidget | None, detail: str) -> str:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("LeadFinder")
    box.setText("LeadFinder couldn't open your workspace.")
    box.setInformativeText(
        f"{detail}\n\nYour data was not deleted. You can restore a backup or try Demo Mode."
    )
    folder_btn = box.addButton(OPEN_DATA, QMessageBox.ButtonRole.ActionRole)
    restore_btn = box.addButton(RESTORE, QMessageBox.ButtonRole.ActionRole)
    demo_btn = box.addButton(OPEN_DEMO, QMessageBox.ButtonRole.ActionRole)
    box.addButton(EXIT, QMessageBox.ButtonRole.RejectRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked is folder_btn:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))
        return CHOICE_FOLDER
    if clicked is restore_btn:
        return CHOICE_RESTORE
    if clicked is demo_btn:
        return CHOICE_DEMO
    return CHOICE_EXIT
