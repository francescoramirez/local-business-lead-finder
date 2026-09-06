from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from leadfinder.ai.models import DEFAULT_GROQ_MODEL, DEFAULT_OUTPUT_LANGUAGE, SalesPrepResult
from leadfinder.ai.provider import ai_configured, groq_model


class SalesPrepPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.result: SalesPrepResult | None = None
        self.generate_count = 0

        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        self.notice = QLabel(
            "Clicking Generate sends commercial signals for this selected lead to the "
            "configured AI provider. Discovery and scoring do not use AI."
        )
        self.notice.setObjectName("hint")
        self.notice.setWordWrap(True)
        self.language = QComboBox()
        self.language.addItem("Spanish", "Spanish")
        self.language.addItem("English", "English")
        self.model = QLineEdit()
        self.model.setPlaceholderText(DEFAULT_GROQ_MODEL)
        self.generate_btn = QPushButton("Generate sales prep")
        self.regenerate_btn = QPushButton("Regenerate")
        self.copy_opener_btn = QPushButton("Copy opener")
        self.copy_points_btn = QPushButton("Copy talking points")
        self.copy_full_btn = QPushButton("Copy full prep")
        self.save_notes_btn = QPushButton("Save to notes")
        self.busy = QLabel("")
        self.observed = QPlainTextEdit()
        self.observed.setReadOnly(True)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.angle = QPlainTextEdit()
        self.angle.setReadOnly(True)
        self.props = QPlainTextEdit()
        self.props.setReadOnly(True)
        self.opener = QTextEdit()
        self.opener.setPlaceholderText("Suggested draft — review before you send anything.")
        self.points = QPlainTextEdit()
        self.points.setReadOnly(True)
        self.objections = QPlainTextEdit()
        self.objections.setReadOnly(True)
        self.cautions = QPlainTextEdit()
        self.cautions.setReadOnly(True)
        self.next_step = QPlainTextEdit()
        self.next_step.setReadOnly(True)
        for widget in (
            self.observed,
            self.summary,
            self.angle,
            self.props,
            self.points,
            self.objections,
            self.cautions,
            self.next_step,
        ):
            widget.setMaximumHeight(90)
        self.opener.setMaximumHeight(110)

        form = QFormLayout()
        form.addRow("Output language", self.language)
        form.addRow("Model", self.model)
        buttons = QHBoxLayout()
        buttons.addWidget(self.generate_btn)
        buttons.addWidget(self.regenerate_btn)
        copy = QHBoxLayout()
        copy.addWidget(self.copy_opener_btn)
        copy.addWidget(self.copy_points_btn)
        copy.addWidget(self.copy_full_btn)
        copy.addWidget(self.save_notes_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.status)
        layout.addWidget(self.notice)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.busy)
        layout.addWidget(QLabel("Observed"))
        layout.addWidget(self.observed)
        layout.addWidget(QLabel("Opportunity summary"))
        layout.addWidget(self.summary)
        layout.addWidget(QLabel("Pitch angle"))
        layout.addWidget(self.angle)
        layout.addWidget(QLabel("Value props"))
        layout.addWidget(self.props)
        layout.addWidget(QLabel("Suggested draft"))
        layout.addWidget(self.opener)
        layout.addWidget(QLabel("Talking points"))
        layout.addWidget(self.points)
        layout.addWidget(QLabel("Likely objections"))
        layout.addWidget(self.objections)
        layout.addWidget(QLabel("Cautions"))
        layout.addWidget(self.cautions)
        layout.addWidget(QLabel("Next step"))
        layout.addWidget(self.next_step)
        layout.addLayout(copy)
        self.refresh_status()
        self.clear_output()

    def refresh_status(self) -> None:
        model = groq_model(self.model.text())
        if ai_configured():
            self.status.setText(f"AI Provider: Groq · Model: {model} · Status: Configured")
        else:
            self.status.setText(
                "AI sales prep is not configured.\n\nSet GROQ_API_KEY to enable it."
            )

    def language_value(self) -> str:
        return str(self.language.currentData() or DEFAULT_OUTPUT_LANGUAGE)

    def model_value(self) -> str:
        return self.model.text().strip()

    def set_busy(self, busy: bool) -> None:
        self.generate_btn.setEnabled(not busy)
        self.regenerate_btn.setEnabled(not busy)
        self.busy.setText("Preparing sales notes…" if busy else "")

    def show_error(self, message: str) -> None:
        self.set_busy(False)
        self.busy.setText(message)

    def clear_output(self) -> None:
        self.result = None
        self.observed.setPlainText("")
        self.summary.setPlainText("")
        self.angle.setPlainText("")
        self.props.setPlainText("")
        self.opener.setPlainText("")
        self.points.setPlainText("")
        self.objections.setPlainText("")
        self.cautions.setPlainText("")
        self.next_step.setPlainText("")

    def show_result(self, result: SalesPrepResult) -> None:
        self.result = result
        self.set_busy(False)
        self.busy.setText("")
        self.observed.setPlainText("\n".join(f"• {item}" for item in result.observed))
        self.summary.setPlainText(result.opportunity_summary)
        self.angle.setPlainText(result.pitch_angle)
        self.props.setPlainText("\n".join(f"• {item}" for item in result.value_props))
        self.opener.setPlainText(result.opening_message)
        self.points.setPlainText("\n".join(f"• {item}" for item in result.talking_points))
        self.objections.setPlainText("\n".join(f"• {item}" for item in result.objections))
        self.cautions.setPlainText("\n".join(f"• {item}" for item in result.cautions))
        gaps = f"\n{result.information_gaps}" if result.information_gaps else ""
        self.next_step.setPlainText(result.next_step + gaps)

    def current_full_text(self) -> str:
        return "\n\n".join(
            [
                "Observed\n" + self.observed.toPlainText(),
                "Opportunity summary\n" + self.summary.toPlainText(),
                "Pitch angle\n" + self.angle.toPlainText(),
                "Value props\n" + self.props.toPlainText(),
                "Suggested draft\n" + self.opener.toPlainText(),
                "Talking points\n" + self.points.toPlainText(),
                "Cautions\n" + self.cautions.toPlainText(),
                "Next step\n" + self.next_step.toPlainText(),
            ]
        )

    def copy_text(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None and text.strip():
            clipboard.setText(text)

