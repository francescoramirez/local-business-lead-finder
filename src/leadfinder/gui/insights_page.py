from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from leadfinder.analytics import format_rate
from leadfinder.insights import InsightsReport, SegmentInsight, format_segment_line, format_uplift
from leadfinder.models import Campaign


class InsightsPage(QWidget):
    explain_requested = Signal()
    create_experiment_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._strongest: SegmentInsight | None = None
        self.period = QComboBox()
        self.period.addItem("Last 7 days", 7)
        self.period.addItem("Last 30 days", 30)
        self.period.addItem("Last 90 days", 90)
        self.period.addItem("All time", 0)
        self.period.setCurrentIndex(1)
        self.campaign = QComboBox()
        self.empty = QLabel(
            "Not enough history yet.\n\n"
            "Contact prospects and record outcomes to compare segments against baseline."
        )
        self.empty.setObjectName("empty")
        self.empty.setWordWrap(True)
        self.baseline = QLabel("")
        self.baseline.setWordWrap(True)
        self.strongest = QLabel("")
        self.strongest.setWordWrap(True)
        self.weakest = QLabel("")
        self.weakest.setWordWrap(True)
        self.segments = QPlainTextEdit()
        self.segments.setReadOnly(True)
        self.experiment = QLabel("")
        self.experiment.setWordWrap(True)
        self.explanation = QPlainTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setPlaceholderText(
            "Optional. Explain with AI sends aggregated metrics only — never individual leads."
        )
        self.refresh_btn = QPushButton("Refresh")
        self.export_btn = QPushButton("Export insights")
        self.explain_btn = QPushButton("Explain insights")
        self.create_btn = QPushButton("Create experiment")
        self.create_btn.setEnabled(False)

        filters = QFormLayout()
        filters.addRow("Period", self.period)
        filters.addRow("Campaign", self.campaign)
        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_btn)
        buttons.addWidget(self.export_btn)
        buttons.addWidget(self.explain_btn)
        buttons.addWidget(self.create_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addLayout(buttons)
        layout.addWidget(self.empty)
        box = QGroupBox("Baseline")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(self.baseline)
        layout.addWidget(box)
        top = QGroupBox("Strongest observed segment")
        top_layout = QVBoxLayout(top)
        top_layout.addWidget(self.strongest)
        layout.addWidget(top)
        low = QGroupBox("Lower observed conversion")
        low_layout = QVBoxLayout(low)
        low_layout.addWidget(self.weakest)
        layout.addWidget(low)
        segs = QGroupBox("Segments")
        segs_layout = QVBoxLayout(segs)
        segs_layout.addWidget(self.segments)
        layout.addWidget(segs)
        exp = QGroupBox("Suggested next experiment")
        exp_layout = QVBoxLayout(exp)
        exp_layout.addWidget(self.experiment)
        layout.addWidget(exp)
        ai = QGroupBox("AI explanation (optional)")
        ai_layout = QVBoxLayout(ai)
        ai_layout.addWidget(self.explanation)
        layout.addWidget(ai)

        self.explain_btn.clicked.connect(self.explain_requested.emit)
        self.create_btn.clicked.connect(self._emit_create)

    def selected_campaign_id(self) -> int | None:
        value = self.campaign.currentData()
        if not value:
            return None
        return int(value)

    def fill_campaigns(self, campaigns: list[Campaign]) -> None:
        current = self.campaign.currentData()
        self.campaign.blockSignals(True)
        self.campaign.clear()
        self.campaign.addItem("All campaigns", 0)
        for campaign in campaigns:
            self.campaign.addItem(campaign.name, campaign.id)
        index = self.campaign.findData(current)
        self.campaign.setCurrentIndex(max(index, 0))
        self.campaign.blockSignals(False)

    def show_report(self, report: InsightsReport) -> None:
        self._strongest = report.strongest
        self.empty.setVisible(report.empty)
        self.create_btn.setEnabled(report.strongest is not None)
        self.baseline.setText(
            f"Overall contact -> interest  {format_rate(report.baseline)}\n"
            f"n={report.baseline.denominator} · {report.period_label}\n"
            f"{report.campaign_name}\n"
            "Uplift is shown in percentage points, not relative percent."
        )
        if report.strongest:
            row = report.strongest
            self.strongest.setText(
                f"{row.label}\n{row.rate}%  {format_uplift(row.uplift_pp)} vs baseline\n"
                f"n={row.n}  ·  confidence {row.confidence}  ·  {row.metric}"
            )
        else:
            self.strongest.setText("No qualifying segment yet.")
        if report.weakest:
            row = report.weakest
            self.weakest.setText(
                f"{row.label}\n{row.rate}%  {format_uplift(row.uplift_pp)} vs baseline\n"
                f"n={row.n}  ·  confidence {row.confidence}"
            )
        else:
            self.weakest.setText("No qualifying segment yet.")
        lines = []
        for row in report.ranked:
            lines.append(format_segment_line(row))
        if report.combinations:
            lines.append("")
            lines.append("Two-dimension combinations")
            for row in report.combinations:
                lines.append(format_segment_line(row))
        self.segments.setPlainText("\n".join(lines) or "No ranked segments.")
        self.experiment.setText(report.suggested_experiment)

    def show_explanation(self, text: str) -> None:
        self.explanation.setPlainText(text)

    def _emit_create(self) -> None:
        if self._strongest is not None:
            self.create_experiment_requested.emit(self._strongest)
