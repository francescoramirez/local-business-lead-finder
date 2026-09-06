from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from leadfinder.application.service import matches_filters
from leadfinder.gui.formatters import format_when
from leadfinder.models import CONTACT_STATUS_LABELS, ManagedLead
from leadfinder.workflow import is_overdue

COLUMNS = (
    "Opportunity",
    "Score",
    "Business",
    "Phone",
    "Digital Presence",
    "Website",
    "Rating",
    "Reviews",
    "Contact Status",
    "Follow-up",
    "Last activity",
)

WEBSITE_LABELS = {
    "no_website": "No website",
    "has_website": "Website",
    "social_only": "Social only",
    "link_aggregator": "Link aggregator",
    "unreachable": "Unreachable",
    "non_https": "HTTP only",
    "parked": "Parked",
    "weak_website": "Weak website",
    "unknown": "Unknown",
}

OPPORTUNITY_LABELS = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


class LeadTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[ManagedLead] = []

    def set_leads(self, rows: list[ManagedLead]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def leads(self) -> list[ManagedLead]:
        return list(self._rows)

    def lead_at(self, row: int) -> ManagedLead | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def update_row(self, item: ManagedLead) -> None:
        for index, current in enumerate(self._rows):
            if current.lead.place_id == item.lead.place_id:
                self._rows[index] = item
                left = self.index(index, 0)
                right = self.index(index, self.columnCount() - 1)
                self.dataChanged.emit(left, right)
                return

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section]
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        item = self._rows[index.row()]
        lead = item.lead
        if role == Qt.ItemDataRole.UserRole:
            return item
        if role == Qt.ItemDataRole.DisplayRole:
            values = [
                OPPORTUNITY_LABELS.get(lead.opportunity_level, lead.opportunity_level),
                lead.opportunity_score,
                lead.name,
                lead.phone,
                WEBSITE_LABELS.get(lead.website_status, lead.website_status),
                lead.website,
                "" if lead.rating is None else f"{lead.rating:.1f}",
                "" if lead.user_rating_count is None else str(lead.user_rating_count),
                CONTACT_STATUS_LABELS.get(item.contact_status, item.contact_status),
                format_when(item.next_follow_up_at),
                format_when(item.last_activity_at),
            ]
            return values[index.column()]
        if role == Qt.ItemDataRole.UserRole + 1:
            follow = item.next_follow_up_at or "9999"
            activity = item.last_activity_at or ""
            keys = [
                lead.opportunity_score,
                lead.opportunity_score,
                lead.name.lower(),
                lead.phone,
                lead.website_status,
                lead.website,
                lead.rating or 0,
                lead.user_rating_count or 0,
                item.contact_status,
                follow,
                activity,
            ]
            return keys[index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in {1, 6, 7}:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and index.column() == 9:
            if is_overdue(item.contact_status, item.next_follow_up_at):
                from PySide6.QtGui import QColor

                return QColor("#b45309")
        return None


class LeadFilterProxy(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self.text = ""
        self.min_score = 0
        self.no_website_only = False
        self.has_phone = False
        self.operational_only = False
        self.contact_status = ""
        self.opportunity_level = ""
        self.presence = ""
        self.follow_up_view = ""
        self.tag = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_filters(
        self,
        *,
        text: str,
        min_score: int,
        no_website_only: bool,
        has_phone: bool,
        operational_only: bool,
        contact_status: str,
        opportunity_level: str = "",
        presence: str = "",
        follow_up_view: str = "",
        tag: str = "",
    ) -> None:
        self.text = text
        self.min_score = min_score
        self.no_website_only = no_website_only
        self.has_phone = has_phone
        self.operational_only = operational_only
        self.contact_status = contact_status
        self.opportunity_level = opportunity_level
        self.presence = presence
        self.follow_up_view = follow_up_view
        self.tag = tag
        self.invalidate()

    def filterAcceptsRow(  # type: ignore[override]
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, LeadTableModel):
            return True
        item = model.lead_at(source_row)
        if item is None:
            return False
        return matches_filters(
            item,
            text=self.text,
            min_score=self.min_score,
            no_website_only=self.no_website_only,
            has_phone=self.has_phone,
            operational_only=self.operational_only,
            contact_status=self.contact_status,
            opportunity_level=self.opportunity_level,
            presence=self.presence,
            follow_up_view=self.follow_up_view,
            tag=self.tag,
        )

    def lead_from_proxy(self, proxy_row: int) -> ManagedLead | None:
        source = self.mapToSource(self.index(proxy_row, 0))
        model = self.sourceModel()
        if not isinstance(model, LeadTableModel):
            return None
        return model.lead_at(source.row())
