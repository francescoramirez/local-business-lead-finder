"""Pitch template picker for Sales Prep. No network, no auto-send."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from leadfinder.templates import PitchTemplate


class PitchTemplatePanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Pitch Template")
        self.selector = QComboBox()
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a template to preview rendered text.")
        self.preview.setMaximumHeight(120)
        self.copy_btn = QPushButton("Copy")
        self.new_btn = QPushButton("New")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        hint = QLabel(
            "Manual templates only. Missing {placeholders} stay visible. Nothing is sent."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        buttons = QHBoxLayout()
        buttons.addWidget(self.copy_btn)
        buttons.addWidget(self.new_btn)
        buttons.addWidget(self.edit_btn)
        buttons.addWidget(self.delete_btn)
        layout = QVBoxLayout(self)
        layout.addWidget(self.selector)
        layout.addWidget(self.preview)
        layout.addLayout(buttons)
        layout.addWidget(hint)

    def selected_id(self) -> int:
        value = self.selector.currentData()
        return int(value) if value else 0

    def selected_body(self) -> str:
        item = self.selector.currentData()
        if item is None:
            return ""
        role = int(Qt.ItemDataRole.UserRole) + 1
        return str(self.selector.itemData(self.selector.currentIndex(), role) or "")

    def reload(self, templates: list[PitchTemplate], *, keep_id: int = 0) -> None:
        current = keep_id or self.selected_id()
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem("No template", 0)
        for template in templates:
            self.selector.addItem(template.name, template.id)
            index = self.selector.count() - 1
            self.selector.setItemData(index, template.body, int(Qt.ItemDataRole.UserRole) + 1)
        found = self.selector.findData(current)
        self.selector.setCurrentIndex(max(found, 0))
        self.selector.blockSignals(False)

    def current_template_body(self) -> str:
        index = self.selector.currentIndex()
        if index <= 0:
            return ""
        role = int(Qt.ItemDataRole.UserRole) + 1
        return str(self.selector.itemData(index, role) or "")
