"""Table filter bar, including named saved filters."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from leadfinder.labels import MANUAL_PRIORITIES, MANUAL_PRIORITY_LABELS
from leadfinder.models import CONTACT_STATUS_LABELS, CONTACT_STATUSES


class FilterBar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.filter_text = QLineEdit()
        self.filter_text.setPlaceholderText("Filter leads…")
        self.min_score = QSpinBox()
        self.min_score.setRange(0, 100)
        self.filter_no_website = QCheckBox("No website")
        self.filter_phone = QCheckBox("Has phone")
        self.filter_operational = QCheckBox("Operational")
        self.filter_operational.setChecked(True)
        self.filter_status = QComboBox()
        self.filter_status.addItem("Any status", "")
        for status in CONTACT_STATUSES:
            self.filter_status.addItem(CONTACT_STATUS_LABELS[status], status)
        self.filter_opportunity = QComboBox()
        self.filter_opportunity.addItem("All opportunities", "")
        self.filter_opportunity.addItem("High", "high")
        self.filter_opportunity.addItem("Medium", "medium")
        self.filter_opportunity.addItem("Low", "low")
        self.filter_presence = QComboBox()
        self.filter_presence.addItem("All presence", "")
        self.filter_presence.addItem("No website", "no_website")
        self.filter_presence.addItem("Social only", "social_only")
        self.filter_presence.addItem("Link aggregator", "link_aggregator")
        self.filter_presence.addItem("Website", "website")
        self.filter_presence.addItem("Unreachable", "unreachable")
        self.filter_follow = QComboBox()
        self.filter_follow.addItem("Any follow-up", "")
        self.filter_follow.addItem("Needs follow-up", "needs")
        self.filter_follow.addItem("Due today", "due_today")
        self.filter_follow.addItem("Overdue", "overdue")
        self.filter_follow.addItem("Upcoming", "upcoming")
        self.filter_follow.addItem("No follow-up", "none")
        self.filter_priority = QComboBox()
        self.filter_priority.addItem("Any priority", "")
        for value in MANUAL_PRIORITIES:
            self.filter_priority.addItem(MANUAL_PRIORITY_LABELS[value], value)
        self.filter_tag = QLineEdit()
        self.filter_tag.setPlaceholderText("Tag")
        self.filter_tag.setMaximumWidth(120)
        self.saved_filters = QComboBox()
        self.save_filter_btn = QPushButton("Save filter")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Find"))
        layout.addWidget(self.filter_text, 1)
        layout.addWidget(QLabel("Min score"))
        layout.addWidget(self.min_score)
        layout.addWidget(self.filter_opportunity)
        layout.addWidget(self.filter_presence)
        layout.addWidget(self.filter_follow)
        layout.addWidget(self.filter_priority)
        layout.addWidget(self.filter_tag)
        layout.addWidget(self.filter_no_website)
        layout.addWidget(self.filter_phone)
        layout.addWidget(self.filter_operational)
        layout.addWidget(self.filter_status)
        layout.addWidget(self.saved_filters)
        layout.addWidget(self.save_filter_btn)
