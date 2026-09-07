"""Dedicated Settings dialog. Does not store API keys in QSettings."""

from __future__ import annotations

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from leadfinder.desktop.credentials import (
    SOURCE_ENVIRONMENT,
    SOURCE_KEYRING,
    SOURCE_TEST,
    delete_secret,
    groq_key_configured,
    keyring_available,
    lookup_groq_key,
    lookup_places_key,
    places_key_configured,
    save_secret,
)
from leadfinder.desktop.identity import REPOSITORY_URL
from leadfinder.desktop.settings_keys import DEFAULT_EXPORT_DIR, DEFAULT_MAX_REQUESTS, DEFAULT_PAGES
from leadfinder.errors import CredentialStoreError
from leadfinder.fields import FIELD_PROFILES
from leadfinder.gui.about_dialog import AboutDialog
from leadfinder.gui.error_dialogs import show_info, show_warning
from leadfinder.paths import data_dir, default_db_path, display_user_path, exports_dir


def _safe_int(settings: QSettings, key: str, default: int) -> int:
    raw = settings.value(key, default)
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return default

HELP_TEXT = (
    "API keys are read from the environment or, when available, the OS credential "
    "store (Windows Credential Manager on Windows).\n\n"
    "Environment variables:\n"
    "  GOOGLE_MAPS_API_KEY or GOOGLE_PLACES_API_KEY\n"
    "  GROQ_API_KEY (optional)\n\n"
    "Keys are never stored in SQLite, QSettings, logs, or workspace ZIP files."
)


def _status_label(source: str, configured: bool) -> str:
    if source == SOURCE_TEST:
        return "Configured (test override)"
    if source == SOURCE_ENVIRONMENT:
        return "Configured via environment"
    if source == SOURCE_KEYRING:
        return "Configured (OS credential store)"
    if configured:
        return "Configured"
    return "Not configured"


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.places_edit: QLineEdit | None = None
        self.groq_edit: QLineEdit | None = None
        self.setWindowTitle("Settings")
        self.resize(560, 460)
        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._api_tab(), "API / Integrations")
        tabs.addTab(self._data_tab(), "Data")
        tabs.addTab(self._about_tab(), "About")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def _general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.default_country = QLineEdit(str(self.settings.value("country", "AR")))
        self.default_country.setMaxLength(2)
        self.default_region = QLineEdit(str(self.settings.value("region", "Buenos Aires")))
        self.default_pages = QSpinBox()
        self.default_pages.setRange(1, 3)
        self.default_pages.setValue(_safe_int(self.settings, DEFAULT_PAGES, 1))
        self.default_max_requests = QSpinBox()
        self.default_max_requests.setRange(1, 500)
        self.default_max_requests.setValue(_safe_int(self.settings, DEFAULT_MAX_REQUESTS, 100))
        self.default_fields = QComboBox()
        self.default_fields.addItems(sorted(FIELD_PROFILES))
        current_fields = str(self.settings.value("fields", "enterprise"))
        index = self.default_fields.findText(current_fields)
        self.default_fields.setCurrentIndex(max(index, 0))
        self.export_dir = QLineEdit(
            str(self.settings.value(DEFAULT_EXPORT_DIR, str(exports_dir())))
        )
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_export)
        export_row = QHBoxLayout()
        export_row.addWidget(self.export_dir, 1)
        export_row.addWidget(browse)
        form.addRow("Default country", self.default_country)
        form.addRow("Default region", self.default_region)
        form.addRow("Default search pages", self.default_pages)
        form.addRow("Default max requests", self.default_max_requests)
        form.addRow("Default field profile", self.default_fields)
        form.addRow("Default export folder", export_row)
        hint = QLabel("These defaults apply to new Search fields. They are not API keys.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        form.addRow(hint)
        return page

    def _api_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        places = lookup_places_key()
        groq = lookup_groq_key()
        self.places_status = QLabel(
            f"Google Places: {_status_label(places.source, places_key_configured())}"
        )
        self.groq_status = QLabel(f"Groq: {_status_label(groq.source, groq_key_configured())}")
        help_body = QLabel(HELP_TEXT)
        help_body.setWordWrap(True)
        layout.addWidget(self.places_status)
        layout.addWidget(self.groq_status)
        layout.addWidget(help_body)
        if keyring_available():
            layout.addWidget(QLabel("Save a key to the OS credential store (not shown again):"))
            self.places_edit = QLineEdit()
            self.places_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.places_edit.setPlaceholderText("Google Places API key")
            self.groq_edit = QLineEdit()
            self.groq_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.groq_edit.setPlaceholderText("Groq API key (optional)")
            layout.addWidget(self.places_edit)
            places_row = QHBoxLayout()
            save_places = QPushButton("Save Places key securely")
            remove_places = QPushButton("Remove Places key")
            save_places.clicked.connect(lambda: self._save_key("places", self.places_edit))
            remove_places.clicked.connect(lambda: self._remove_key("places"))
            places_row.addWidget(save_places)
            places_row.addWidget(remove_places)
            layout.addLayout(places_row)
            layout.addWidget(self.groq_edit)
            groq_row = QHBoxLayout()
            save_groq = QPushButton("Save Groq key securely")
            remove_groq = QPushButton("Remove Groq key")
            save_groq.clicked.connect(lambda: self._save_key("groq", self.groq_edit))
            remove_groq.clicked.connect(lambda: self._remove_key("groq"))
            groq_row.addWidget(save_groq)
            groq_row.addWidget(remove_groq)
            layout.addLayout(groq_row)
            env_note = QLabel(
                "An environment variable, if set, is used first and is not removed here."
            )
            env_note.setObjectName("hint")
            env_note.setWordWrap(True)
            layout.addWidget(env_note)
        else:
            self.places_edit = None
            self.groq_edit = None
            missing = QLabel(
                "OS credential storage is not available in this session. "
                "Use environment variables. Developer machines can also use a local .env file."
            )
            missing.setWordWrap(True)
            layout.addWidget(missing)
            help_btn = QPushButton("Open configuration help")
            help_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPOSITORY_URL)))
            layout.addWidget(help_btn)
        layout.addStretch(1)
        return page

    def _data_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        db = QLabel(f"Database: {display_user_path(default_db_path())}")
        db.setWordWrap(True)
        folder = QLabel(f"Data folder: {display_user_path(data_dir())}")
        folder.setWordWrap(True)
        layout.addWidget(db)
        layout.addWidget(folder)
        open_btn = QPushButton("Open data folder")
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))
        )
        layout.addWidget(open_btn)
        note = QLabel(
            "Backup, restore, and workspace export live in the File menu. "
            "Uninstalling LeadFinder does not delete this folder."
        )
        note.setWordWrap(True)
        note.setObjectName("hint")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        open_about = QPushButton("Open About")
        open_about.clicked.connect(self._open_about)
        restart = QPushButton("Show welcome again")
        restart.clicked.connect(self._restart_onboarding)
        layout.addWidget(open_about)
        layout.addWidget(restart)
        layout.addStretch(1)
        return page

    def _open_about(self) -> None:
        AboutDialog(self).exec()

    def _restart_onboarding(self) -> None:
        from leadfinder.desktop.settings_keys import ONBOARDING_COMPLETED

        self.settings.setValue(ONBOARDING_COMPLETED, False)
        show_info(
            self,
            "Welcome",
            "Welcome will be shown the next time LeadFinder starts, "
            "or choose Help → Show Welcome now.",
        )

    def _browse_export(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Default export folder", self.export_dir.text()
        )
        if path:
            self.export_dir.setText(path)

    def _refresh_api_status(self) -> None:
        places = lookup_places_key()
        groq = lookup_groq_key()
        self.places_status.setText(
            f"Google Places: {_status_label(places.source, bool(places.value))}"
        )
        self.groq_status.setText(f"Groq: {_status_label(groq.source, bool(groq.value))}")

    def _save_key(self, kind: str, editor: QLineEdit | None) -> None:
        if editor is None:
            return
        value = editor.text()
        try:
            save_secret(kind, value)
        except CredentialStoreError as error:
            show_warning(self, "API key", str(error))
            return
        editor.clear()
        self._refresh_api_status()
        show_info(self, "API key", "Saved to the OS credential store. The key is not shown again.")

    def _remove_key(self, kind: str) -> None:
        try:
            delete_secret(kind)
        except CredentialStoreError as error:
            show_warning(self, "API key", str(error))
            return
        self._refresh_api_status()
        show_info(self, "API key", "Removed from the OS credential store, if it was saved there.")

    def _save(self) -> None:
        self.settings.setValue("country", self.default_country.text().strip().upper() or "AR")
        self.settings.setValue("region", self.default_region.text().strip())
        self.settings.setValue(DEFAULT_PAGES, self.default_pages.value())
        self.settings.setValue(DEFAULT_MAX_REQUESTS, self.default_max_requests.value())
        self.settings.setValue("fields", self.default_fields.currentText())
        export = self.export_dir.text().strip()
        if export:
            self.settings.setValue(DEFAULT_EXPORT_DIR, export)
        self.settings.sync()
        self.accept()
