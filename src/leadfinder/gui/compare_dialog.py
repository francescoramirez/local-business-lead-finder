"""Compare a few in-memory leads. Does not persist phone or website."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from leadfinder.duplicates import duplicate_hint_text
from leadfinder.gui.formatters import format_when
from leadfinder.labels import MANUAL_PRIORITY_LABELS, OPPORTUNITY_LABELS, PRESENCE_LABELS
from leadfinder.models import CONTACT_STATUS_LABELS, LocalLeadState, ManagedLead

COMPARE_FIELDS = (
    "Business",
    "Opportunity",
    "Manual priority",
    "Digital presence",
    "Website status",
    "Rating",
    "Reviews",
    "Contact status",
    "Follow-up",
    "Previously seen",
    "Duplicate hint",
)

MAX_COMPARE = 5


def compare_rows(
    items: list[ManagedLead],
    *,
    session: list[ManagedLead],
    local: list[LocalLeadState] | None = None,
) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in items[:MAX_COMPARE]:
        lead = item.lead
        hint = duplicate_hint_text(item, session, local)
        rows.append(
            [
                lead.name or item.label or "(unnamed)",
                OPPORTUNITY_LABELS.get(lead.opportunity_level, lead.opportunity_level),
                MANUAL_PRIORITY_LABELS.get(item.manual_priority, item.manual_priority),
                PRESENCE_LABELS.get(lead.website_status, lead.website_status),
                lead.website_status or "—",
                "—" if lead.rating is None else f"{lead.rating:.1f}",
                "—" if lead.user_rating_count is None else str(lead.user_rating_count),
                CONTACT_STATUS_LABELS.get(item.contact_status, item.contact_status),
                format_when(item.next_follow_up_at),
                "Yes" if item.previously_seen else "No",
                hint.replace("\n", " · ") if hint else "—",
            ]
        )
    return rows


class CompareDialog(QDialog):
    def __init__(self, items: list[ManagedLead], rows: list[list[str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Compare selected")
        self.resize(900, 360)
        table = QTableWidget(len(COMPARE_FIELDS), len(items))
        table.setVerticalHeaderLabels(list(COMPARE_FIELDS))
        table.setHorizontalHeaderLabels(
            [item.lead.name or item.label or "(unnamed)" for item in items]
        )
        for col, values in enumerate(rows):
            for row, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        hint = QLabel(
            "Decision aid only. Phone and website stay in session memory and are not stored here."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(table)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self.table = table
