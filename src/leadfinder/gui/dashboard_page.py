from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from leadfinder.models import SearchRun
from leadfinder.workflow import PipelineCounts


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.overdue_banner = QLabel("")
        self.overdue_banner.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.metrics = QLabel("")
        self.funnel = QLabel("")
        self.conversions = QLabel("")
        self.recent = QPlainTextEdit()
        self.recent.setReadOnly(True)
        self.demo_guide = QLabel(
            "Demo checklist\n"
            "1. Select a lead\n"
            "2. Set priority High\n"
            "3. Mark Contacted\n"
            "4. Add follow-up\n"
            "5. Open Analytics"
        )
        self.demo_guide.setWordWrap(True)
        self.demo_guide.setVisible(False)
        layout = QVBoxLayout(self)
        layout.addWidget(self.overdue_banner)
        layout.addWidget(self.demo_guide)
        box = QGroupBox("Pipeline")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(self.metrics)
        box_layout.addWidget(self.funnel)
        box_layout.addWidget(self.conversions)
        layout.addWidget(box)
        history = QGroupBox("Recent searches")
        history_layout = QVBoxLayout(history)
        history_layout.addWidget(self.recent)
        layout.addWidget(history)

    def refresh(
        self,
        counts: PipelineCounts,
        conversions: dict[str, float | None],
        searches: list[SearchRun],
    ) -> None:
        overdue = counts.overdue
        self.overdue_banner.setText(
            f"{overdue} overdue follow-up{'s' if overdue != 1 else ''}"
            if overdue
            else "No overdue follow-ups"
        )
        self.metrics.setText(
            "\n".join(
                [
                    f"Total prospects: {counts.total}",
                    f"High opportunity: {counts.high_opportunity}",
                    f"New: {counts.new}",
                    f"Contacted: {counts.contacted}",
                    f"Interested: {counts.interested}",
                    f"Follow-ups due today: {counts.due_today}",
                    f"Overdue: {counts.overdue}",
                    f"Won: {counts.won}",
                ]
            )
        )
        self.funnel.setText(
            "Funnel\n"
            f"Found        {counts.total}\n"
            f"Contacted    {counts.contacted + counts.interested + counts.follow_up + counts.won}\n"
            f"Interested   {counts.interested + counts.follow_up + counts.won}\n"
            f"Won          {counts.won}"
        )
        contacted = conversions.get("contacted_to_interested")
        won = conversions.get("interested_to_won")
        conv_lines = ["Conversions"]
        conv_lines.append(
            f"Contacted → Interested: {contacted}%"
            if contacted is not None
            else "Contacted → Interested: not enough data"
        )
        conv_lines.append(
            f"Interested → Won: {won}%" if won is not None else "Interested → Won: not enough data"
        )
        self.conversions.setText("\n".join(conv_lines))
        if not searches:
            self.recent.setPlainText("No searches recorded yet.")
            return
        lines = []
        for run in searches:
            lines.append(
                f"{run.created_at[:10]} · {run.business_preset} · {run.location} · "
                f"{run.lead_count} leads"
            )
        self.recent.setPlainText("\n".join(lines))

    def set_demo_guide(self, visible: bool) -> None:
        self.demo_guide.setVisible(visible)
