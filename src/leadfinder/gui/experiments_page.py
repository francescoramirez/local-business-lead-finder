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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from leadfinder.analytics import format_rate
from leadfinder.experiments import ExperimentMetrics
from leadfinder.models import Experiment


class ExperimentsPage(QWidget):
    refresh_requested = Signal()
    summarize_requested = Signal(object)
    save_notes_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._metrics: list[ExperimentMetrics] = []
        self._experiments: dict[int, Experiment] = {}
        self.empty = QLabel(
            "No experiments yet.\n\n"
            "Create one from Insights to test a hypothesis, then associate a campaign "
            "after you search. LeadFinder will not run a search for you."
        )
        self.empty.setObjectName("empty")
        self.empty.setWordWrap(True)
        self.cards = QVBoxLayout()
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Hypothesis observations and conclusion (saved locally).")
        self.status = QComboBox()
        for value in ("draft", "active", "completed", "archived"):
            self.status.addItem(value.title(), value)
        self.save_btn = QPushButton("Save notes")
        self.summarize_btn = QPushButton("Summarize experiment")
        self.refresh_btn = QPushButton("Refresh")
        self._current_id: int | None = None

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.summarize_btn)
        form = QFormLayout()
        form.addRow("Status", self.status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        holder.setLayout(self.cards)
        scroll.setWidget(holder)

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.empty)
        layout.addWidget(scroll, 2)
        layout.addLayout(form)
        layout.addWidget(self.detail, 1)
        notes_box = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_box)
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_box, 1)

        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self.save_btn.clicked.connect(self._save)
        self.summarize_btn.clicked.connect(self._summarize)

    def show_experiments(
        self,
        experiments: list[Experiment],
        metrics: list[ExperimentMetrics],
    ) -> None:
        self._experiments = {item.id: item for item in experiments}
        self._metrics = metrics
        self.empty.setVisible(not experiments)
        while self.cards.count():
            item = self.cards.takeAt(0)
            widget = None if item is None else item.widget()
            if widget is not None:
                widget.deleteLater()
        for row in metrics:
            card = QGroupBox(row.name)
            body = QLabel(
                f"{row.target_label or 'All matching leads'}\n"
                f"{row.status.title()}  ·  n={row.sample}\n"
                f"Contact->Interest: {format_rate(row.observed)}\n"
                f"Baseline: {format_rate(row.baseline)}\n"
                f"{row.evaluation}"
            )
            body.setWordWrap(True)
            inner = QVBoxLayout(card)
            inner.addWidget(body)
            open_btn = QPushButton("Open")
            open_btn.clicked.connect(lambda _=False, eid=row.experiment_id: self._select(eid))
            inner.addWidget(open_btn)
            self.cards.addWidget(card)
        self.cards.addStretch()
        if metrics and self._current_id is None:
            self._select(metrics[0].experiment_id)
        elif self._current_id is not None:
            self._select(self._current_id)

    def _select(self, experiment_id: int) -> None:
        self._current_id = experiment_id
        experiment = self._experiments.get(experiment_id)
        metrics = next((row for row in self._metrics if row.experiment_id == experiment_id), None)
        if experiment is None or metrics is None:
            return
        index = self.status.findData(experiment.status)
        if index >= 0:
            self.status.setCurrentIndex(index)
        self.detail.setPlainText(
            f"{experiment.name} [{experiment.status}]\n"
            f"Target: {metrics.target_label}\n"
            f"Period: {metrics.period_label}\n"
            f"Hypothesis: {experiment.hypothesis or '(none)'}\n\n"
            f"Baseline: {format_rate(metrics.baseline)} n={metrics.baseline.denominator}\n"
            f"Observed: {format_rate(metrics.observed)} n={metrics.sample}\n"
            f"Difference: "
            f"{'n/a' if metrics.difference_pp is None else str(metrics.difference_pp) + ' pp'}\n"
            f"Evaluation: {metrics.evaluation}\n\n"
            "Descriptive comparison only. This is not a causal claim or A/B test."
        )
        self.notes.setPlainText(
            "\n\n".join(
                part
                for part in (experiment.hypothesis, experiment.observations, experiment.conclusion)
                if part
            )
        )

    def _save(self) -> None:
        experiment = self._experiments.get(self._current_id or 0)
        if experiment is None:
            return
        experiment.status = str(self.status.currentData() or experiment.status)
        experiment.observations = self.notes.toPlainText().strip()
        self.save_notes_requested.emit(experiment)

    def _summarize(self) -> None:
        metrics = next(
            (row for row in self._metrics if row.experiment_id == self._current_id),
            None,
        )
        if metrics is not None:
            self.summarize_requested.emit(metrics)
