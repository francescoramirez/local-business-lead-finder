from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from leadfinder.gui.formatters import format_when
from leadfinder.models import LocalLeadState
from leadfinder.workflow import CONTACT_STATUS_LABELS


class ProspectsPage(QWidget):
    selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Label", "Status", "Follow-up", "Tags", "First seen", "Last seen"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._emit)
        hint = QLabel(
            "Select a row to open workflow details on the Search tab "
            "(status, priority, follow-up, undo)."
        )
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.table)

    def _emit(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        if item is not None:
            self.selected.emit(str(item.data(Qt.ItemDataRole.UserRole) or ""))

    def set_states(self, rows: list[LocalLeadState]) -> None:
        self.table.setRowCount(len(rows))
        for index, state in enumerate(rows):
            label = QTableWidgetItem(state.label or state.place_id)
            label.setData(Qt.ItemDataRole.UserRole, state.place_id)
            status_label = CONTACT_STATUS_LABELS.get(state.contact_status, state.contact_status)
            values = [
                label,
                QTableWidgetItem(status_label),
                QTableWidgetItem(format_when(state.next_follow_up_at)),
                QTableWidgetItem(state.tags),
                QTableWidgetItem(format_when(state.first_seen_at)),
                QTableWidgetItem(format_when(state.last_seen_at)),
            ]
            for column, cell in enumerate(values):
                self.table.setItem(index, column, cell)
        self.table.resizeColumnsToContents()
