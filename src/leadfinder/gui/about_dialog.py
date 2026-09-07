"""About dialog. Version comes from leadfinder.__version__."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from leadfinder.desktop.diagnostics import collect_diagnostics
from leadfinder.desktop.identity import (
    APP_DISPLAY_NAME,
    LICENSE_NAME,
    REPOSITORY_URL,
    application_version,
)
from leadfinder.paths import data_dir, display_user_path


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_DISPLAY_NAME}")
        self.resize(460, 320)
        title = QLabel(APP_DISPLAY_NAME)
        title.setObjectName("title")
        version = QLabel(f"Version {application_version()}")
        body = QLabel(
            "Local-first business prospecting workflow.\n"
            f"{LICENSE_NAME}\n\n"
            "No cloud account. No telemetry. No automatic outreach."
        )
        body.setWordWrap(True)
        data = QLabel(f"Data folder: {display_user_path(data_dir())}")
        data.setWordWrap(True)
        data.setObjectName("hint")

        repo_btn = QPushButton("Repository")
        repo_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPOSITORY_URL)))
        copy_btn = QPushButton("Copy diagnostics")
        copy_btn.clicked.connect(self._copy)
        folder_btn = QPushButton("Open data folder")
        folder_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))
        )
        row = QHBoxLayout()
        row.addWidget(repo_btn)
        row.addWidget(folder_btn)
        row.addWidget(copy_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(body)
        layout.addWidget(data)
        layout.addLayout(row)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def _copy(self) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(collect_diagnostics())
