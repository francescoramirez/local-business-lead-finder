from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from leadfinder.analytics import AnalyticsReport, format_rate
from leadfinder.application.service import LeadService
from leadfinder.costs.models import LIST_COST_DISCLAIMER
from leadfinder.models import Campaign


class AnalyticsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.period = QComboBox()
        self.period.addItem("Last 7 days", 7)
        self.period.addItem("Last 30 days", 30)
        self.period.addItem("Last 90 days", 90)
        self.period.addItem("All time", 0)
        self.period.addItem("Custom", -1)
        self.period.setCurrentIndex(1)
        self.campaign = QComboBox()
        self.compare_a = QComboBox()
        self.compare_b = QComboBox()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.empty = QLabel(
            "Not enough history yet.\n\n"
            "Contact prospects and record outcomes to unlock campaign analytics."
        )
        self.empty.setObjectName("empty")
        self.empty.setWordWrap(True)
        self.headline = QLabel("")
        self.headline.setWordWrap(True)
        self.rates = QLabel("")
        self.rates.setWordWrap(True)
        self.rates.setToolTip(
            "Contact → Interested: percentage of prospects that reached Interested "
            "after being contacted at least once. Hidden until n≥3."
        )
        self.snapshot = QLabel("")
        self.segments = QPlainTextEdit()
        self.segments.setReadOnly(True)
        self.compare = QPlainTextEdit()
        self.compare.setReadOnly(True)
        self.observations = QLabel("")
        self.observations.setWordWrap(True)
        self.cost_label = QLabel("")
        self.cost_label.setObjectName("hint")
        self.cost_label.setWordWrap(True)
        self.cost_label.setToolTip(LIST_COST_DISCLAIMER)
        self.export_btn = QPushButton("Export report")
        self.refresh_btn = QPushButton("Refresh")

        filters = QFormLayout()
        filters.addRow("Period", self.period)
        dates = QHBoxLayout()
        dates.addWidget(self.start_date)
        dates.addWidget(self.end_date)
        filters.addRow("Custom range", dates)
        filters.addRow("Campaign", self.campaign)
        compare_row = QHBoxLayout()
        compare_row.addWidget(self.compare_a)
        compare_row.addWidget(self.compare_b)
        filters.addRow("Compare campaigns", compare_row)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_btn)
        buttons.addWidget(self.export_btn)
        layout.addLayout(buttons)
        layout.addWidget(self.empty)
        box = QGroupBox("Historical conversions")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(self.headline)
        box_layout.addWidget(self.rates)
        layout.addWidget(box)
        snap = QGroupBox("Current pipeline snapshot")
        snap_layout = QVBoxLayout(snap)
        snap_layout.addWidget(self.snapshot)
        layout.addWidget(snap)
        segs = QGroupBox("Segments")
        segs_layout = QVBoxLayout(segs)
        segs_layout.addWidget(self.segments)
        layout.addWidget(segs)
        cmp_box = QGroupBox("Campaign comparison")
        cmp_layout = QVBoxLayout(cmp_box)
        cmp_layout.addWidget(self.compare)
        layout.addWidget(cmp_box)
        costs = QGroupBox("Campaign API estimate")
        costs_layout = QVBoxLayout(costs)
        costs_layout.addWidget(self.cost_label)
        layout.addWidget(costs)
        layout.addWidget(self.observations)

    def selected_campaign_id(self) -> int | None:
        value = self.campaign.currentData()
        if not value:
            return None
        return int(value)

    def fill_campaigns(self, campaigns: list[Campaign]) -> None:
        def refill(combo: QComboBox, *, include_all: bool) -> None:
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            if include_all:
                combo.addItem("All campaigns", 0)
            for campaign in campaigns:
                combo.addItem(campaign.name, campaign.id)
            index = combo.findData(current)
            combo.setCurrentIndex(max(index, 0))
            combo.blockSignals(False)

        refill(self.campaign, include_all=True)
        refill(self.compare_a, include_all=False)
        refill(self.compare_b, include_all=False)
        if self.compare_b.count() > 1:
            self.compare_b.setCurrentIndex(1)

    def show_report(
        self, report: AnalyticsReport, comparison: str = "", cost_text: str = ""
    ) -> None:
        empty = report.historical.total_leads == 0
        self.empty.setVisible(empty)
        hist = report.historical
        self.headline.setText(
            f"Leads {hist.total_leads}    Contacted {hist.contacted_once}    "
            f"Interested {hist.interested_once}    Won {hist.won_once}\n"
            f"{report.period_label} · {report.campaign_name}"
        )
        self.rates.setText(
            f"Contact rate {format_rate(report.contact_rate)}    "
            f"Contact → Interested {format_rate(report.contact_to_interest)}    "
            f"Contact → Win {format_rate(report.contact_to_win)}    "
            f"Interest → Win {format_rate(report.interest_to_win)}"
        )
        snap = report.snapshot
        self.snapshot.setText(
            f"New {snap.new} · Contacted {snap.contacted} · Interested {snap.interested} · "
            f"Follow-up {snap.follow_up} · Won {snap.won} · Overdue {snap.overdue_followups}"
        )
        blocks = [
            _table("Business type", report.by_business),
            _table("Digital presence", report.by_presence),
            _table("Locations", report.by_location),
            _table("Opportunity", report.by_opportunity),
        ]
        if report.by_method:
            method_lines = [
                "Contact method (unique leads with that method)",
                "Method | Leads | Interested | Won",
            ]
            for row in report.by_method:
                method_lines.append(f"{row.label} | {row.leads} | {row.interested} | {row.won}")
            blocks.append("\n".join(method_lines))
        if report.weekly:
            week_lines = ["Weekly trend", "Week | Leads | Contacted | Interested | Won"]
            for week_row in report.weekly:
                week_lines.append(
                    f"{week_row.week_start} | {week_row.leads} | {week_row.contacted} | "
                    f"{week_row.interested} | {week_row.won}"
                )
            blocks.append("\n".join(week_lines))
        if report.ai_prep_saved:
            blocks.append(
                "AI sales prep saved (correlation only — no causal claim)\n"
                f"Leads {report.ai_prep_saved} · Interested {report.ai_prep_interested} · "
                f"Won {report.ai_prep_won}"
            )
        self.segments.setPlainText("\n\n".join(blocks))
        self.compare.setPlainText(comparison)
        self.cost_label.setText(cost_text or "Estimated list cost: Unknown")
        self.observations.setText("\n".join(report.observations))


def _table(title: str, rows: list) -> str:
    lines = [title, "Segment | Leads | Contacted | Interested | Won | Contact→Interest"]
    if not rows:
        lines.append("(no data)")
        return "\n".join(lines)
    for row in rows:
        if row.contact_to_interest is None:
            rate = "Not enough data"
        else:
            rate = f"{row.contact_to_interest}%"
        lines.append(
            f"{row.label} | {row.leads} | {row.contacted} | "
            f"{row.interested} | {row.won} | {rate}"
        )
    return "\n".join(lines)


def custom_bounds(page: AnalyticsPage) -> tuple[datetime, datetime]:
    start_raw = page.start_date.date().toPython()
    end_raw = page.end_date.date().toPython()
    start_day = start_raw if isinstance(start_raw, date) else date.today()
    end_day = end_raw if isinstance(end_raw, date) else date.today()
    start = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_day, time.max, tzinfo=timezone.utc)
    return start, end


def export_report_dialog(parent: QWidget, service: LeadService, report: AnalyticsReport) -> None:
    path, _selected = QFileDialog.getSaveFileName(
        parent,
        "Export report",
        "campaign-report.md",
        "Markdown (*.md);;JSON (*.json);;CSV (*.csv)",
    )
    if not path:
        return
    service.export_analytics(report, Path(path))
