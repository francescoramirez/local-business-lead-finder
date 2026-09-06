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
