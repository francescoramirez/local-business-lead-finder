from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from leadfinder.workflow import (
    ACTIVITY_TYPE_LABELS,
    CONTACT_METHOD_LABELS,
    CONTACT_METHODS,
    OUTCOME_LABELS,
    OUTCOMES,
    ActivityType,
    shift_iso,
)


class FollowUpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Schedule follow-up")
        self._iso = ""
        self.custom = QDateTimeEdit()
        self.custom.setCalendarPopup(True)
        self.custom.setDateTime(QDateTime.currentDateTime().addDays(1))
        buttons = QHBoxLayout()
        for label, days in (("Tomorrow", 1), ("In 3 days", 3), ("In 1 week", 7)):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, d=days: self._pick_days(d))
            buttons.addWidget(btn)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._accept_custom)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.custom)
        layout.addWidget(box)

    def _pick_days(self, days: int) -> None:
        self._iso = shift_iso(days)
        self.accept()

    def _accept_custom(self) -> None:
        stamp = self.custom.dateTime().toSecsSinceEpoch()
        due = datetime.fromtimestamp(stamp, tz=timezone.utc).replace(microsecond=0)
        self._iso = due.isoformat()
        self.accept()

    def iso_value(self) -> str:
        return self._iso


class ActivityDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add activity")
        self.activity_type = QComboBox()
        for key, label in ACTIVITY_TYPE_LABELS.items():
            if key == ActivityType.DISCOVERED.value:
                continue
            if key == ActivityType.SALES_PREP_SAVED.value:
                continue
            self.activity_type.addItem(label, key)
        self.method = QComboBox()
        self.method.addItem("—", "")
        for key in CONTACT_METHODS:
            self.method.addItem(CONTACT_METHOD_LABELS[key], key)
        self.outcome = QComboBox()
        self.outcome.addItem("—", "")
        for key in OUTCOMES:
            self.outcome.addItem(OUTCOME_LABELS[key], key)
        self.note = QTextEdit()
        form = QFormLayout()
        form.addRow("Type", self.activity_type)
        form.addRow("Method", self.method)
        form.addRow("Outcome", self.outcome)
        form.addRow("Note", self.note)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(box)


class CampaignDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Campaign")
        self.name = QLineEdit()
        self.preset = QLineEdit()
        self.location = QLineEdit()
        self.region = QLineEdit()
        self.country = QLineEdit()
        self.country.setMaxLength(2)
        self.notes = QTextEdit()
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Business preset", self.preset)
        form.addRow("Location", self.location)
        form.addRow("Region", self.region)
        form.addRow("Country", self.country)
        form.addRow("Notes", self.notes)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(box)


class TagDialog(QDialog):
    def __init__(self, current: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tags")
        self.edit = QLineEdit(current)
        self.edit.setPlaceholderText("priority, call, local-client")
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.edit)
        layout.addWidget(box)


class ExperimentDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        name: str = "",
        hypothesis: str = "",
        business_preset: str = "",
        location: str = "",
        digital_presence: str = "",
        opportunity_level: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create experiment")
        self.name = QLineEdit(name)
        self.hypothesis = QTextEdit()
        self.hypothesis.setPlainText(hypothesis)
        self.preset = QLineEdit(business_preset)
        self.location = QLineEdit(location)
        self.presence = QLineEdit(digital_presence)
        self.opportunity = QLineEdit(opportunity_level)
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Hypothesis", self.hypothesis)
        form.addRow("Business preset", self.preset)
        form.addRow("Location", self.location)
        form.addRow("Digital presence", self.presence)
        form.addRow("Opportunity", self.opportunity)
        hint = QLabel(
            "Review these criteria before searching. Creating an experiment does not run a search."
        )
        hint.setWordWrap(True)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(box)


class TemplateDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        name: str = "",
        body: str = "",
        business_type: str = "",
        presence_type: str = "",
        language: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pitch template")
        self.name = QLineEdit(name)
        self.body = QTextEdit()
        self.body.setPlainText(body)
        self.business_type = QLineEdit(business_type)
        self.presence_type = QLineEdit(presence_type)
        self.language = QLineEdit(language)
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Body", self.body)
        form.addRow("Business type", self.business_type)
        form.addRow("Presence type", self.presence_type)
        form.addRow("Language", self.language)
        hint = QLabel(
            "Placeholders: {business_name} {business_type} {location} {region} "
            "{country} {presence_type} {opportunity_level}. Missing tokens stay visible."
        )
        hint.setWordWrap(True)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(box)
