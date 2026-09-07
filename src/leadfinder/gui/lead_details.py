"""Selected-lead overview, workflow controls, and Sales Prep tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from leadfinder.gui.sales_prep import SalesPrepPanel
from leadfinder.labels import MANUAL_PRIORITIES, MANUAL_PRIORITY_LABELS
from leadfinder.models import CONTACT_STATUS_LABELS, CONTACT_STATUSES


class LeadDetailsPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Lead details")
        self.detail_name = QLabel("Select a lead")
        self.detail_name.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.detail_score = QLabel("")
        self.detail_reason = QLabel("")
        self.detail_reason.setWordWrap(True)
        self.detail_reason.setObjectName("hint")
        self.detail_presence = QLabel("")
        self.detail_presence.setWordWrap(True)
        self.detail_meta = QLabel("")
        self.detail_meta.setWordWrap(True)
        self.detail_seen = QLabel("")
        self.detail_duplicate = QLabel("")
        self.detail_duplicate.setObjectName("hint")
        self.open_maps = QPushButton("Open in Google Maps")
        self.open_maps.setEnabled(False)
        self.open_website = QPushButton("Open website")
        self.open_website.setEnabled(False)
        self.mark_contacted_btn = QPushButton("Mark contacted")
        self.mark_interested_btn = QPushButton("Mark interested")
        self.schedule_btn = QPushButton("Schedule follow-up")
        self.activity_btn = QPushButton("Add activity")
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setEnabled(False)
        self.copy_phone_btn = QPushButton("Copy phone")
        self.copy_phone_btn.setEnabled(False)
        self.copy_pitch_btn = QPushButton("Copy pitch")
        self.contact_status = QComboBox()
        for status in CONTACT_STATUSES:
            self.contact_status.addItem(CONTACT_STATUS_LABELS[status], status)
        self.manual_priority = QComboBox()
        for value in MANUAL_PRIORITIES:
            self.manual_priority.addItem(MANUAL_PRIORITY_LABELS[value], value)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Notes are saved automatically.")
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("tags, comma-separated")
        self.follow_label = QLabel("No follow-up scheduled")
        self.detail_activity = QPlainTextEdit()
        self.detail_activity.setReadOnly(True)
        self.detail_activity.setMaximumHeight(140)

        overview = QWidget()
        details_layout = QVBoxLayout(overview)
        details_layout.addWidget(QLabel("Overview"))
        details_layout.addWidget(self.detail_name)
        details_layout.addWidget(self.detail_score)
        details_layout.addWidget(self.detail_reason)
        details_layout.addWidget(self.detail_duplicate)
        details_layout.addWidget(self.detail_meta)
        details_layout.addWidget(self.detail_seen)
        details_layout.addWidget(QLabel("Digital presence"))
        details_layout.addWidget(self.detail_presence)
        actions = QHBoxLayout()
        actions.addWidget(self.mark_contacted_btn)
        actions.addWidget(self.mark_interested_btn)
        actions.addWidget(self.schedule_btn)
        actions.addWidget(self.activity_btn)
        actions.addWidget(self.undo_btn)
        details_layout.addLayout(actions)
        extras = QHBoxLayout()
        extras.addWidget(self.copy_phone_btn)
        extras.addWidget(self.copy_pitch_btn)
        details_layout.addLayout(extras)
        links = QHBoxLayout()
        links.addWidget(self.open_maps)
        links.addWidget(self.open_website)
        details_layout.addLayout(links)
        details_layout.addWidget(QLabel("Workflow"))
        details_form = QFormLayout()
        details_form.addRow("Contact status", self.contact_status)
        details_form.addRow("Priority", self.manual_priority)
        details_form.addRow("Next follow-up", self.follow_label)
        details_form.addRow("Tags", self.tags_edit)
        details_layout.addLayout(details_form)
        details_layout.addWidget(QLabel("Notes"))
        details_layout.addWidget(self.notes)
        details_layout.addWidget(QLabel("Activity"))
        details_layout.addWidget(self.detail_activity)

        self.sales_prep = SalesPrepPanel()
        prep_scroll = QScrollArea()
        prep_scroll.setWidgetResizable(True)
        prep_scroll.setWidget(self.sales_prep)
        self.detail_tabs = QTabWidget()
        self.detail_tabs.addTab(overview, "Overview")
        self.detail_tabs.addTab(prep_scroll, "Sales Prep")
        outer = QVBoxLayout(self)
        outer.addWidget(self.detail_tabs)
