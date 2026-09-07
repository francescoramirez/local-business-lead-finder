"""First-run onboarding. Short, non-blocking, no API calls."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from leadfinder.desktop.credentials import places_key_configured
from leadfinder.desktop.identity import APP_DISPLAY_NAME, application_version
from leadfinder.desktop.settings_keys import ONBOARDING_COMPLETED

WELCOME_BODY = (
    "Discover and qualify local business prospects, track outreach manually, "
    "and learn from your results.\n\nYour workflow data stays on this computer."
)
FLOW_BODY = (
    "Discover\n"
    "↓\n"
    "Qualify\n"
    "↓\n"
    "Prioritize\n"
    "↓\n"
    "Contact manually\n"
    "↓\n"
    "Track\n"
    "↓\n"
    "Learn\n\n"
    "LeadFinder does not send messages automatically."
)


class OnboardingDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_DISPLAY_NAME}")
        self.setModal(True)
        self.resize(520, 420)
        self.choice = "workspace"
        self.import_path: Path | None = None

        self.stack = QStackedWidget()
        self.stack.addWidget(self._welcome_page())
        self.stack.addWidget(self._flow_page())
        self.stack.addWidget(self._places_page())
        self.stack.addWidget(self._demo_page())

        self.back_btn = QPushButton("Back")
        self.next_btn = QPushButton("Get Started")
        self.next_btn.setObjectName("primary")
        self.back_btn.clicked.connect(self._back)
        self.next_btn.clicked.connect(self._next)
        nav = QHBoxLayout()
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack, 1)
        layout.addLayout(nav)
        self._sync_nav()

    def _welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel(f"Welcome to {APP_DISPLAY_NAME}")
        title.setObjectName("title")
        body = QLabel(WELCOME_BODY)
        body.setWordWrap(True)
        hint = QLabel(f"Version {application_version()}  ·  Local-first  ·  {APP_DISPLAY_NAME}")
        hint.setObjectName("hint")
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        layout.addWidget(hint)
        return page

    def _flow_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("How it works")
        title.setObjectName("title")
        body = QLabel(FLOW_BODY)
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _places_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Google Places API")
        title.setObjectName("title")
        configured = places_key_configured()
        status = QLabel("Configured" if configured else "Not configured")
        status.setObjectName("hint")
        body = QLabel(
            "Required only for real business searches.\n\n"
            "You can configure a key later in Settings. Demo Mode needs no key and "
            "does not call Google or Groq."
        )
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(status)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _demo_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Try LeadFinder")
        title.setObjectName("title")
        body = QLabel(
            "Demo Mode loads synthetic businesses on this computer. "
            "It does not use your workspace database or any API."
        )
        body.setWordWrap(True)
        self.demo_check = QCheckBox("Open Demo Mode after this welcome")
        self.demo_check.setChecked(True)
        import_btn = QPushButton("Import existing workspace…")
        import_btn.clicked.connect(self._pick_import)
        self.import_label = QLabel("")
        self.import_label.setObjectName("hint")
        self.import_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.demo_check)
        layout.addWidget(import_btn)
        layout.addWidget(self.import_label)
        layout.addStretch(1)
        return page

    def _pick_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import workspace", str(Path.home()), "Workspace ZIP (*.zip)"
        )
        if not path:
            return
        self.import_path = Path(path)
        self.demo_check.setChecked(False)
        self.import_label.setText(f"Will import: {self.import_path.name}")

    def _sync_nav(self) -> None:
        index = self.stack.currentIndex()
        self.back_btn.setEnabled(index > 0)
        labels = ["Get Started", "Continue", "Configure later", "Finish"]
        self.next_btn.setText(labels[index])

    def _back(self) -> None:
        index = self.stack.currentIndex()
        if index > 0:
            self.stack.setCurrentIndex(index - 1)
            self._sync_nav()

    def _next(self) -> None:
        index = self.stack.currentIndex()
        if index < self.stack.count() - 1:
            self.stack.setCurrentIndex(index + 1)
            self._sync_nav()
            return
        if self.import_path is not None:
            self.choice = "import"
        elif self.demo_check.isChecked():
            self.choice = "demo"
        else:
            self.choice = "workspace"
        self.accept()


def onboarding_completed(settings: QSettings) -> bool:
    return settings.value(ONBOARDING_COMPLETED, False, type=bool) is True


def mark_onboarding_completed(settings: QSettings) -> None:
    settings.setValue(ONBOARDING_COMPLETED, True)


def run_onboarding(parent: QWidget | None, settings: QSettings) -> OnboardingDialog:
    dialog = OnboardingDialog(parent)
    dialog.exec()
    mark_onboarding_completed(settings)
    return dialog
