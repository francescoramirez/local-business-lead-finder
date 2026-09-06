from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from leadfinder.gui.formatters import format_when
from leadfinder.gui.lead_model import OPPORTUNITY_LABELS
from leadfinder.models import ManagedLead
from leadfinder.workflow import CONTACT_STATUS_LABELS, PIPELINE_COLUMNS, is_overdue


class PipelineColumn(QListWidget):
    dropped = Signal(str, str)

    def __init__(self, status: str) -> None:
        super().__init__()
        self.status = status
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, supported_actions) -> None:  # noqa: N802
        del supported_actions
        item = self.currentItem()
        if item is None:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        place_id = event.mimeData().text().strip()
        if place_id:
            self.dropped.emit(place_id, self.status)
            event.acceptProposedAction()


class PipelinePage(QWidget):
    status_dropped = Signal(str, str)
    card_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.columns: dict[str, PipelineColumn] = {}
        layout = QHBoxLayout(self)
        for status in PIPELINE_COLUMNS:
            column = PipelineColumn(status)
            column.dropped.connect(self.status_dropped.emit)
            column.itemClicked.connect(self._on_item)
            self.columns[status] = column
            wrap = QWidget()
            col_layout = QVBoxLayout(wrap)
            title = QLabel(CONTACT_STATUS_LABELS[status])
            title.setStyleSheet("font-weight: 700;")
            col_layout.addWidget(title)
            col_layout.addWidget(column)
            layout.addWidget(wrap)

    def _on_item(self, item: QListWidgetItem) -> None:
        self.card_selected.emit(str(item.data(Qt.ItemDataRole.UserRole) or ""))

    def set_leads(self, items: list[ManagedLead]) -> None:
        for column in self.columns.values():
            column.clear()
        for item in items:
            target = self.columns.get(item.contact_status)
            if target is None:
                continue
            opportunity = OPPORTUNITY_LABELS.get(
                item.lead.opportunity_level, item.lead.opportunity_level or "—"
            )
            phone = "Phone" if item.lead.contactable else "No phone"
            follow = format_when(item.next_follow_up_at)
            if is_overdue(item.contact_status, item.next_follow_up_at):
                follow = f"Overdue · {follow}"
            text = f"{item.lead.name or item.label}\n{opportunity} · {phone}\n{follow}"
            card = QListWidgetItem(text)
            card.setData(Qt.ItemDataRole.UserRole, item.lead.place_id)
            target.addItem(card)
