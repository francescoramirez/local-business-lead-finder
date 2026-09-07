"""Left-hand search form, cost preview, progress, and summary."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from leadfinder.costs.models import LIST_COST_DISCLAIMER
from leadfinder.fields import FIELD_PROFILES
from leadfinder.presets import list_presets


class SearchPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.preset = QComboBox()
        for preset in list_presets():
            self.preset.addItem(preset.display_label(), preset.name)
        self.location = QLineEdit()
        self.location.setPlaceholderText("Mar del Plata")
        self.region = QLineEdit()
        self.region.setPlaceholderText("Buenos Aires")
        self.country = QLineEdit()
        self.country.setMaxLength(2)
        self.coverage = QComboBox()
        self.coverage.addItems(["budget", "balanced", "full"])
        self.fields = QComboBox()
        self.fields.addItems(sorted(FIELD_PROFILES))
        self.fields.setCurrentText("enterprise")
        self.max_requests = QSpinBox()
        self.max_requests.setRange(1, 500)
        self.max_requests.setValue(100)
        self.pages = QSpinBox()
        self.pages.setRange(1, 3)
        self.pages.setValue(1)
        self.analyze = QCheckBox("Analyze websites")
        self.only_no_website = QCheckBox("No website only")
        self.dry_run_btn = QPushButton("Dry Run")
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primary")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_json_btn = QPushButton("Export JSON")
        self.export_visible = QCheckBox("Export visible rows only")
        self.export_visible.setChecked(True)
        self.analyze_now_btn = QPushButton("Analyze websites")
        self.export_pipeline_btn = QPushButton("Export pipeline")
        self.campaign = QComboBox()
        self.new_campaign_btn = QPushButton("New Campaign")

        target_form = QFormLayout()
        target_form.addRow("Business", self.preset)
        target_form.addRow("Location", self.location)
        target_form.addRow("Region", self.region)
        target_form.addRow("Country", self.country)
        campaign_row = QHBoxLayout()
        campaign_row.addWidget(self.campaign, 1)
        campaign_row.addWidget(self.new_campaign_btn)
        target_form.addRow("Campaign", campaign_row)
        target_box = QGroupBox("Target")
        target_box.setLayout(target_form)

        cost_form = QFormLayout()
        cost_form.addRow("Coverage", self.coverage)
        cost_form.addRow("Fields", self.fields)
        cost_form.addRow("Max requests", self.max_requests)
        cost_form.addRow("Pages", self.pages)
        self.cost_preview = QLabel("Dry Run to preview request volume.")
        self.cost_preview.setObjectName("hint")
        self.cost_preview.setWordWrap(True)
        self.cost_preview.setToolTip(LIST_COST_DISCLAIMER)
        cost_form.addRow(self.cost_preview)
        cost_box = QGroupBox("Cost and volume")
        cost_box.setLayout(cost_form)

        filter_form = QFormLayout()
        filter_form.addRow(self.analyze)
        filter_form.addRow(self.only_no_website)
        filter_box = QGroupBox("Qualification")
        filter_box.setLayout(filter_form)

        buttons = QGridLayout()
        buttons.addWidget(self.dry_run_btn, 0, 0)
        buttons.addWidget(self.search_btn, 0, 1)
        buttons.addWidget(self.cancel_btn, 1, 0)
        buttons.addWidget(self.export_csv_btn, 1, 1)
        buttons.addWidget(self.export_json_btn, 2, 0)
        buttons.addWidget(self.analyze_now_btn, 2, 1)
        buttons.addWidget(self.export_visible, 3, 0)
        buttons.addWidget(self.export_pipeline_btn, 3, 1)
        search_box = QGroupBox("Search")
        search_layout = QVBoxLayout(search_box)
        search_layout.addWidget(target_box)
        search_layout.addWidget(cost_box)
        search_layout.addWidget(filter_box)
        search_layout.addLayout(buttons)
        search_layout.addStretch()

        self.ai_status = QLabel("")
        self.ai_status.setObjectName("hint")
        self.ai_status.setWordWrap(True)
        ai_box = QGroupBox("AI")
        ai_layout = QVBoxLayout(ai_box)
        ai_layout.addWidget(self.ai_status)

        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlaceholderText("Run Dry Run to preview cost, or Search to load leads.")
        summary_box = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.addWidget(self.summary)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress_label = QLabel("Idle")
        self.progress_label.setObjectName("hint")
        self.counters = QLabel("Requests 0  ·  Places 0  ·  Leads 0")
        self.counters.setObjectName("hint")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(search_box, 3)
        layout.addWidget(ai_box, 0)
        layout.addWidget(summary_box, 2)
        layout.addWidget(self.progress)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.counters)
