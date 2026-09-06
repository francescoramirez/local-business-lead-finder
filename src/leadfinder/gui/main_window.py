from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableView,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from leadfinder.ai.models import DEFAULT_OUTPUT_LANGUAGE, SalesPrepResult
from leadfinder.ai.provider import ai_configured, groq_model
from leadfinder.application.service import LeadService, friendly_error
from leadfinder.config import SearchConfig
from leadfinder.errors import ConfigError, LeadFinderError, MissingApiKeyError
from leadfinder.fields import FIELD_PROFILES
from leadfinder.gui.dashboard_page import DashboardPage
from leadfinder.gui.dialogs import ActivityDialog, FollowUpDialog
from leadfinder.gui.formatters import format_when
from leadfinder.gui.lead_model import (
    OPPORTUNITY_LABELS,
    WEBSITE_LABELS,
    LeadFilterProxy,
    LeadTableModel,
)
from leadfinder.gui.pipeline_page import PipelinePage
from leadfinder.gui.prospects_page import ProspectsPage
from leadfinder.gui.sales_prep import SalesPrepPanel
from leadfinder.gui.workers import AnalyzeWorker, SalesPrepWorker, SearchWorker
from leadfinder.models import (
    CONTACT_STATUS_LABELS,
    CONTACT_STATUSES,
    ManagedLead,
    SearchPlan,
    SearchProgress,
    SearchReport,
)
from leadfinder.presets import list_presets
from leadfinder.workflow import ACTIVITY_TYPE_LABELS, ContactStatus


class MainWindow(QMainWindow):
    def __init__(self, service: LeadService | None = None) -> None:
        super().__init__()
        self.setWindowTitle("LeadFinder")
        self.resize(1280, 800)
        self.service = service or LeadService()
        self.settings = QSettings("LeadFinder", "LeadFinder")
        self._worker: SearchWorker | AnalyzeWorker | None = None
        self._prep_worker: SalesPrepWorker | None = None
        self._prep_cache: dict[str, SalesPrepResult] = {}
        self._selected: ManagedLead | None = None
        self._updating_details = False
        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(400)
        self._notes_timer.timeout.connect(self._save_notes)

        self.model = LeadTableModel()
        self.proxy = LeadFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole + 1)

        self._build_ui()
        self._connect()
        self._restore_settings()
        self._apply_filters()
        self._update_empty_state()
        self._refresh_secondary()

    def _build_ui(self) -> None:
        header = QLabel("LeadFinder")
        header.setObjectName("title")
        subtitle = QLabel("Discover, rank, and track local business opportunities.")
        subtitle.setObjectName("hint")

        self.preset = QComboBox()
        for preset in list_presets():
            self.preset.addItem(preset.display_label(), preset.name)
        self.location = QLineEdit()
        self.location.setPlaceholderText("Mar del Plata")
        self.region = QLineEdit()
        self.region.setPlaceholderText("Buenos Aires")
        self.country = QLineEdit()
        self.country.setMaxLength(2)
        self.coverage = QComboBox()
        self.coverage.addItems(["budget", "balanced", "full"])
        self.fields = QComboBox()
        self.fields.addItems(sorted(FIELD_PROFILES))
        self.fields.setCurrentText("enterprise")
        self.max_requests = QSpinBox()
        self.max_requests.setRange(1, 500)
        self.max_requests.setValue(100)
        self.pages = QSpinBox()
        self.pages.setRange(1, 3)
        self.pages.setValue(1)
        self.analyze = QCheckBox("Analyze websites")
        self.only_no_website = QCheckBox("No website only")
        self.dry_run_btn = QPushButton("Dry Run")
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primary")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_json_btn = QPushButton("Export JSON")
        self.export_visible = QCheckBox("Export visible rows only")
        self.export_visible.setChecked(True)
        self.analyze_now_btn = QPushButton("Analyze websites")
        self.export_pipeline_btn = QPushButton("Export pipeline")

        form = QFormLayout()
        form.addRow("Business", self.preset)
        form.addRow("Location", self.location)
        form.addRow("Region", self.region)
        form.addRow("Country", self.country)
        form.addRow("Coverage", self.coverage)
        form.addRow("Fields", self.fields)
        form.addRow("Max requests", self.max_requests)
        form.addRow("Pages", self.pages)
        form.addRow(self.analyze)
        form.addRow(self.only_no_website)
        buttons = QGridLayout()
        buttons.addWidget(self.dry_run_btn, 0, 0)
        buttons.addWidget(self.search_btn, 0, 1)
        buttons.addWidget(self.cancel_btn, 1, 0)
        buttons.addWidget(self.export_csv_btn, 1, 1)
        buttons.addWidget(self.export_json_btn, 2, 0)
        buttons.addWidget(self.analyze_now_btn, 2, 1)
        buttons.addWidget(self.export_visible, 3, 0)
        buttons.addWidget(self.export_pipeline_btn, 3, 1)
        search_box = QGroupBox("Search")
        search_layout = QVBoxLayout(search_box)
        search_layout.addLayout(form)
        search_layout.addLayout(buttons)
        search_layout.addStretch()

        self.ai_status = QLabel("")
        self.ai_status.setObjectName("hint")
        self.ai_status.setWordWrap(True)
        ai_box = QGroupBox("AI")
        ai_layout = QVBoxLayout(ai_box)
        ai_layout.addWidget(self.ai_status)

        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlaceholderText("Run Dry Run to preview cost, or Search to load leads.")
        summary_box = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.addWidget(self.summary)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress_label = QLabel("Idle")
        self.progress_label.setObjectName("hint")
        self.counters = QLabel("Requests 0  ·  Places 0  ·  Leads 0")
        self.counters.setObjectName("hint")

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(search_box, 3)
        left_layout.addWidget(ai_box, 0)
        left_layout.addWidget(summary_box, 2)
        left_layout.addWidget(self.progress)
        left_layout.addWidget(self.progress_label)
        left_layout.addWidget(self.counters)

        self.filter_text = QLineEdit()
        self.filter_text.setPlaceholderText("Filter leads…")
        self.min_score = QSpinBox()
        self.min_score.setRange(0, 100)
        self.filter_no_website = QCheckBox("No website")
        self.filter_phone = QCheckBox("Has phone")
        self.filter_operational = QCheckBox("Operational")
        self.filter_operational.setChecked(True)
        self.filter_status = QComboBox()
        self.filter_status.addItem("Any status", "")
        for status in CONTACT_STATUSES:
            self.filter_status.addItem(CONTACT_STATUS_LABELS[status], status)
        self.filter_opportunity = QComboBox()
        self.filter_opportunity.addItem("All opportunities", "")
        self.filter_opportunity.addItem("High", "high")
        self.filter_opportunity.addItem("Medium", "medium")
        self.filter_opportunity.addItem("Low", "low")
        self.filter_presence = QComboBox()
        self.filter_presence.addItem("All presence", "")
        self.filter_presence.addItem("No website", "no_website")
        self.filter_presence.addItem("Social only", "social_only")
        self.filter_presence.addItem("Link aggregator", "link_aggregator")
        self.filter_presence.addItem("Website", "website")
        self.filter_presence.addItem("Unreachable", "unreachable")
        self.filter_follow = QComboBox()
        self.filter_follow.addItem("Any follow-up", "")
        self.filter_follow.addItem("Needs follow-up", "needs")
        self.filter_follow.addItem("Due today", "due_today")
        self.filter_follow.addItem("Overdue", "overdue")
        self.filter_follow.addItem("Upcoming", "upcoming")
        self.filter_follow.addItem("No follow-up", "none")
        self.filter_tag = QLineEdit()
        self.filter_tag.setPlaceholderText("Tag")
        self.filter_tag.setMaximumWidth(120)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Find"))
        filters.addWidget(self.filter_text, 1)
        filters.addWidget(QLabel("Min score"))
        filters.addWidget(self.min_score)
        filters.addWidget(self.filter_opportunity)
        filters.addWidget(self.filter_presence)
        filters.addWidget(self.filter_follow)
        filters.addWidget(self.filter_tag)
        filters.addWidget(self.filter_no_website)
        filters.addWidget(self.filter_phone)
        filters.addWidget(self.filter_operational)
        filters.addWidget(self.filter_status)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(1, 180)
        self.empty = QLabel(
            "No leads yet.\n\nConfigure a business search and run Dry Run or Search."
        )
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        table_wrap = QWidget()
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addLayout(filters)
        table_layout.addWidget(self.table)
        table_layout.addWidget(self.empty)

        self.detail_name = QLabel("Select a lead")
        self.detail_name.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.detail_score = QLabel("")
        self.detail_reason = QLabel("")
        self.detail_reason.setWordWrap(True)
        self.detail_reason.setObjectName("hint")
        self.detail_presence = QLabel("")
        self.detail_presence.setWordWrap(True)
        self.detail_meta = QLabel("")
        self.detail_meta.setWordWrap(True)
        self.detail_seen = QLabel("")
        self.open_maps = QPushButton("Open in Google Maps")
        self.open_maps.setEnabled(False)
        self.open_website = QPushButton("Open website")
        self.open_website.setEnabled(False)
        self.mark_contacted_btn = QPushButton("Mark contacted")
        self.mark_interested_btn = QPushButton("Mark interested")
        self.schedule_btn = QPushButton("Schedule follow-up")
        self.activity_btn = QPushButton("Add activity")
        self.contact_status = QComboBox()
        for status in CONTACT_STATUSES:
            self.contact_status.addItem(CONTACT_STATUS_LABELS[status], status)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Notes are saved automatically.")
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("tags, comma-separated")
        self.follow_label = QLabel("No follow-up scheduled")
        self.detail_activity = QPlainTextEdit()
        self.detail_activity.setReadOnly(True)
        self.detail_activity.setMaximumHeight(140)
        overview = QWidget()
        details_layout = QVBoxLayout(overview)
        details_layout.addWidget(QLabel("Overview"))
        details_layout.addWidget(self.detail_name)
        details_layout.addWidget(self.detail_score)
        details_layout.addWidget(self.detail_reason)
        details_layout.addWidget(self.detail_meta)
        details_layout.addWidget(self.detail_seen)
        details_layout.addWidget(QLabel("Digital presence"))
        details_layout.addWidget(self.detail_presence)
        actions = QHBoxLayout()
        actions.addWidget(self.mark_contacted_btn)
        actions.addWidget(self.mark_interested_btn)
        actions.addWidget(self.schedule_btn)
        actions.addWidget(self.activity_btn)
        details_layout.addLayout(actions)
        links = QHBoxLayout()
        links.addWidget(self.open_maps)
        links.addWidget(self.open_website)
        details_layout.addLayout(links)
        details_layout.addWidget(QLabel("Workflow"))
        details_form = QFormLayout()
        details_form.addRow("Contact status", self.contact_status)
        details_form.addRow("Next follow-up", self.follow_label)
        details_form.addRow("Tags", self.tags_edit)
        details_layout.addLayout(details_form)
        details_layout.addWidget(QLabel("Notes"))
        details_layout.addWidget(self.notes)
        details_layout.addWidget(QLabel("Activity"))
        details_layout.addWidget(self.detail_activity)

        self.sales_prep = SalesPrepPanel()
        prep_scroll = QScrollArea()
        prep_scroll.setWidgetResizable(True)
        prep_scroll.setWidget(self.sales_prep)
        self.detail_tabs = QTabWidget()
        self.detail_tabs.addTab(overview, "Overview")
        self.detail_tabs.addTab(prep_scroll, "Sales Prep")
        details = QGroupBox("Lead details")
        details_outer = QVBoxLayout(details)
        details_outer.addWidget(self.detail_tabs)
        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.addWidget(table_wrap)
        right_split.addWidget(details)
        right_split.setStretchFactor(0, 3)
        right_split.setStretchFactor(1, 2)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right_split)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([340, 940])

        self.pipeline_page = PipelinePage()
        self.prospects_page = ProspectsPage()
        self.dashboard_page = DashboardPage()
        self.tabs = QTabWidget()
        self.tabs.addTab(split, "Search")
        self.tabs.addTab(self.pipeline_page, "Pipeline")
        self.tabs.addTab(self.prospects_page, "Prospects")
        self.tabs.addTab(self.dashboard_page, "Dashboard")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        find_action = QAction("Find", self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.triggered.connect(self.filter_text.setFocus)
        self.addAction(find_action)
        search_action = QAction("Search", self)
        search_action.setShortcut(QKeySequence("Ctrl+R"))
        search_action.triggered.connect(self.start_search)
        self.addAction(search_action)
        export_action = QAction("Export", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(lambda: self.export_leads("csv"))
        self.addAction(export_action)
        backup_action = QAction("Backup local data", self)
        backup_action.triggered.connect(self.backup_db)
        self.addAction(backup_action)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(export_action)
        file_menu.addAction(backup_action)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _connect(self) -> None:
        self.dry_run_btn.clicked.connect(self.run_dry_run)
        self.search_btn.clicked.connect(self.start_search)
        self.cancel_btn.clicked.connect(self.cancel_search)
        self.analyze_now_btn.clicked.connect(self.start_analyze)
        self.export_csv_btn.clicked.connect(lambda: self.export_leads("csv"))
        self.export_json_btn.clicked.connect(lambda: self.export_leads("json"))
        self.export_pipeline_btn.clicked.connect(self.export_pipeline)
        self.filter_text.textChanged.connect(self._apply_filters)
        self.min_score.valueChanged.connect(self._apply_filters)
        self.filter_no_website.toggled.connect(self._apply_filters)
        self.filter_phone.toggled.connect(self._apply_filters)
        self.filter_operational.toggled.connect(self._apply_filters)
        self.filter_status.currentIndexChanged.connect(self._apply_filters)
        self.filter_opportunity.currentIndexChanged.connect(self._apply_filters)
        self.filter_presence.currentIndexChanged.connect(self._apply_filters)
        self.filter_follow.currentIndexChanged.connect(self._apply_filters)
        self.filter_tag.textChanged.connect(self._apply_filters)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self.table.customContextMenuRequested.connect(self._table_menu)
        self.contact_status.currentIndexChanged.connect(self._on_status_changed)
        self.notes.textChanged.connect(self._schedule_notes_save)
        self.tags_edit.editingFinished.connect(self._save_tags)
        self.open_maps.clicked.connect(self._open_maps)
        self.open_website.clicked.connect(self._open_website)
        self.mark_contacted_btn.clicked.connect(
            lambda: self._quick_status(ContactStatus.CONTACTED.value)
        )
        self.mark_interested_btn.clicked.connect(
            lambda: self._quick_status(ContactStatus.INTERESTED.value)
        )
        self.schedule_btn.clicked.connect(self.schedule_follow_up)
        self.activity_btn.clicked.connect(self.add_activity)
        self.tabs.currentChanged.connect(self._refresh_secondary)
        self.pipeline_page.status_dropped.connect(self._on_pipeline_drop)
        self.pipeline_page.card_selected.connect(self._select_place)
        self.prospects_page.selected.connect(self._select_place)
        self.sales_prep.generate_btn.clicked.connect(self.start_sales_prep)
        self.sales_prep.regenerate_btn.clicked.connect(self.start_sales_prep)
        self.sales_prep.copy_opener_btn.clicked.connect(self._copy_opener)
        self.sales_prep.copy_points_btn.clicked.connect(self._copy_talking_points)
        self.sales_prep.copy_full_btn.clicked.connect(self._copy_full_prep)
        self.sales_prep.save_notes_btn.clicked.connect(self._save_sales_prep_notes)

    def _refresh_ai_status(self) -> None:
        model = groq_model(self.sales_prep.model_value())
        if ai_configured():
            text = (
                f"AI Provider: Groq\nModel: {model}\nStatus: Configured\n\n"
                "Set GROQ_API_KEY in your environment. The key is never shown or saved here."
            )
        else:
            text = (
                "AI Provider: Groq\n"
                f"Model: {model}\n"
                "Status: Not configured\n\n"
                "Set GROQ_API_KEY in your environment"
            )
        self.ai_status.setText(text)
        self.sales_prep.refresh_status()

    def current_config(self) -> SearchConfig:
        location = self.location.text().strip()
        return SearchConfig(
            business=str(self.preset.currentData() or "hotel"),
            locations=[location] if location else [],
            region=self.region.text().strip(),
            country=self.country.text().strip() or "AR",
            coverage=self.coverage.currentText(),
            field_profile=self.fields.currentText(),
            pages=self.pages.value(),
            max_requests=self.max_requests.value(),
            analyze_websites=self.analyze.isChecked(),
            only_no_website=self.only_no_website.isChecked(),
            delay=0.4,
        )

    def run_dry_run(self) -> None:
        try:
            plan = self.service.dry_run(self.current_config())
        except LeadFinderError as error:
            QMessageBox.warning(self, "Dry run", friendly_error(error))
            return
        self.summary.setPlainText(self._plan_text(plan))
        self.statusBar().showMessage("Dry run complete. No API requests were made.")

    def _plan_text(self, plan: SearchPlan) -> str:
        locations = "\n".join(f"  - {item}" for item in plan.locations[:40])
        extra = "" if len(plan.locations) <= 40 else f"\n  … {len(plan.locations) - 40} more"
        return (
            f"Business preset: {plan.business}\n"
            f"Search terms: {', '.join(plan.search_terms)}\n"
            f"Locations: {len(plan.locations)}\n"
            f"Country: {plan.country}\n"
            f"Region: {plan.region or '(none)'}\n"
            f"Coverage: {plan.coverage}\n"
            f"Max queries: {plan.max_queries}\n"
            f"Max API requests: {plan.max_api_requests}\n"
            f"Page size: {plan.page_size}\n"
            f"Pages: {plan.pages}\n"
            f"Field profile: {plan.field_profile}\n"
            f"Billing tier: {plan.billing_tier}\n"
            f"Website analysis: {'yes' if plan.analyze_websites else 'no'}\n\n"
            f"Locations:\n{locations}{extra}\n\n"
            "No API requests were made."
        )

    def start_search(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        try:
            self.current_config().to_plan()
            self.service.require_api_key()
        except MissingApiKeyError as error:
            QMessageBox.warning(self, "API key", friendly_error(error))
            return
        except ConfigError as error:
            QMessageBox.warning(self, "Search", friendly_error(error))
            return
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.progress_label.setText("Searching…")
        self._worker = SearchWorker(self.service, self.current_config(), parent=self)
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_search_done)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.finished.connect(lambda: self._set_busy(False))
        self._worker.start()

    def cancel_search(self) -> None:
        if self._worker:
            self._worker.request_cancel()
            self.progress_label.setText("Cancelling…")

    def start_analyze(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        items = []
        for row in range(self.proxy.rowCount()):
            item = self.proxy.lead_from_proxy(row)
            if item is not None:
                items.append(item)
        if not items:
            QMessageBox.information(
                self,
                "Analyze websites",
                "There are no visible leads to analyze.",
            )
            return
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.progress_label.setText(f"Analyzing websites 0 / {len(items)}")
        self._worker = AnalyzeWorker(self.service, items, parent=self)
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_analyze_done)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.finished.connect(lambda: self._set_busy(False))
        self._worker.start()

    def _on_analyze_done(self, items: list) -> None:
        for item in items:
            self.model.update_row(item)
        self.proxy.invalidate()
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress_label.setText("Website analysis done")
        self.statusBar().showMessage(f"Analyzed {len(items)} websites.")
        if self._selected:
            current = next(
                (item for item in items if item.lead.place_id == self._selected.lead.place_id),
                self._selected,
            )
            self._show_lead(current)

    def _on_progress(self, event: SearchProgress) -> None:
        self.progress_label.setText(event.message)
        self.counters.setText(
            f"Requests {event.api_requests} · Places {event.places_found} "
            f"· Leads {event.leads_count}"
        )

    def _on_search_done(self, report: SearchReport, managed: list) -> None:
        self.model.set_leads(managed)
        self.proxy.sort(1, Qt.SortOrder.DescendingOrder)
        self._update_empty_state()
        cancelled = " (cancelled)" if report.cancelled else ""
        self.summary.setPlainText(
            f"Queries: {report.queries_executed}\n"
            f"API requests: {report.api_requests}\n"
            f"Places found: {report.places_found}\n"
            f"Duplicates discarded: {report.duplicates_discarded}\n"
            f"Operational: {report.operational}\n"
            f"No website: {report.no_website}\n"
            f"Contactable: {report.contactable}\n"
            f"Leads loaded: {len(managed)}{cancelled}"
        )
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress_label.setText("Done" + cancelled)
        self.counters.setText(
            f"Requests {report.api_requests} · Places {report.places_found} · Leads {len(managed)}"
        )
        self.statusBar().showMessage(f"Loaded {len(managed)} leads{cancelled}.")
        if managed:
            self.table.selectRow(0)
        self._refresh_secondary()

    def _on_search_failed(self, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress_label.setText("Failed")
        QMessageBox.critical(self, "Search failed", message)

    def _set_busy(self, busy: bool) -> None:
        self.search_btn.setEnabled(not busy)
        self.dry_run_btn.setEnabled(not busy)
        self.analyze_now_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        if not busy:
            self.progress.setRange(0, 1)

    def _apply_filters(self) -> None:
        self.proxy.set_filters(
            text=self.filter_text.text(),
            min_score=self.min_score.value(),
            no_website_only=self.filter_no_website.isChecked(),
            has_phone=self.filter_phone.isChecked(),
            operational_only=self.filter_operational.isChecked(),
            contact_status=str(self.filter_status.currentData() or ""),
            opportunity_level=str(self.filter_opportunity.currentData() or ""),
            presence=str(self.filter_presence.currentData() or ""),
            follow_up_view=str(self.filter_follow.currentData() or ""),
            tag=self.filter_tag.text(),
        )
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        has_rows = self.proxy.rowCount() > 0
        self.table.setVisible(has_rows or self.model.rowCount() > 0)
        self.empty.setVisible(self.model.rowCount() == 0)

    def _on_selection(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        item = self.proxy.lead_from_proxy(indexes[0].row())
        if item:
            self._show_lead(item)

    def _show_lead(self, item: ManagedLead) -> None:
        self._updating_details = True
        self._selected = item
        lead = item.lead
        website = WEBSITE_LABELS.get(lead.website_status, lead.website_status)
        rating = "—" if lead.rating is None else f"{lead.rating:.1f}"
        reviews = "—" if lead.user_rating_count is None else str(lead.user_rating_count)
        opportunity = OPPORTUNITY_LABELS.get(lead.opportunity_level, lead.opportunity_level)
        https = {"yes": "Yes", "no": "No"}.get(lead.https, "Unknown")
        reachable = {"yes": "Yes", "no": "No"}.get(lead.reachable, "Unknown")
        bullets = [
            part.strip()
            for part in lead.qualification_reason.replace(f"{opportunity} opportunity: ", "")
            .replace("High opportunity: ", "")
            .replace("Medium opportunity: ", "")
            .replace("Low opportunity: ", "")
            .rstrip(".")
            .split(",")
            if part.strip()
        ]
        reason_lines = "\n".join(f"• {item}" for item in bullets) or lead.lead_reason.replace(
            "; ", "\n"
        )
        self.detail_name.setText(lead.name or "(unnamed)")
        self.detail_score.setText(
            f"{opportunity}  ·  Opportunity {lead.opportunity_score}  ·  Lead {lead.lead_score}"
        )
        self.detail_reason.setText(lead.lead_reason.replace("; ", "\n"))
        self.detail_presence.setText(
            "Digital presence\n"
            f"Category: {website}\n"
            f"URL: {lead.final_url or lead.website or '—'}\n"
            f"HTTPS: {https}\n"
            f"Reachable: {reachable}\n\n"
            f"Opportunity: {opportunity}\n\n"
            f"Reasons:\n{reason_lines}"
        )
        self.detail_meta.setText(
            f"{lead.phone or 'No phone'}\n"
            f"{lead.website or 'No website'} ({website})\n"
            f"{lead.address or 'No address'}\n"
            f"Rating {rating}  ·  Reviews {reviews}\n"
            f"{lead.primary_type or lead.place_type or lead.business_preset}\n"
            f"{lead.source_query}"
        )
        seen = "Previously seen" if item.previously_seen else "First time in this workspace"
        if item.contact_status != "new":
            seen += f"  ·  {CONTACT_STATUS_LABELS.get(item.contact_status, item.contact_status)}"
        self.detail_seen.setText(seen)
        self.follow_label.setText(format_when(item.next_follow_up_at))
        self.tags_edit.setText(item.tags)
        self.open_maps.setEnabled(bool(lead.google_maps_url))
        self.open_website.setEnabled(bool(lead.website))
        index = self.contact_status.findData(item.contact_status)
        self.contact_status.setCurrentIndex(max(index, 0))
        self.notes.setPlainText(item.notes)
        self._render_activity(item.lead.place_id)
        cached = self._prep_cache.get(item.lead.place_id)
        if cached is not None:
            self.sales_prep.show_result(cached)
        else:
            self.sales_prep.clear_output()
        self._updating_details = False

    def _on_status_changed(self) -> None:
        if self._updating_details or self._selected is None:
            return
        status = str(self.contact_status.currentData() or "new")
        updated = self.service.set_status(self._selected, status)
        self._selected = updated
        self.model.update_row(updated)
        self._show_lead(updated)
        self._refresh_secondary()

    def _schedule_notes_save(self) -> None:
        if self._updating_details:
            return
        self._notes_timer.start()

    def _save_notes(self) -> None:
        if self._selected is None:
            return
        updated = self.service.set_notes(self._selected, self.notes.toPlainText())
        self._selected = updated
        self.model.update_row(updated)

    def _save_tags(self) -> None:
        if self._updating_details or self._selected is None:
            return
        updated = self.service.set_tags(self._selected, self.tags_edit.text())
        self._selected = updated
        self.model.update_row(updated)
        self._refresh_secondary()

    def _render_activity(self, place_id: str) -> None:
        lines = []
        for activity in self.service.activities(place_id):
            label = ACTIVITY_TYPE_LABELS.get(activity.activity_type, activity.activity_type)
            extra = f" · {activity.note}" if activity.note else ""
            lines.append(f"{format_when(activity.created_at)}\n{label}{extra}")
        self.detail_activity.setPlainText("\n\n".join(lines) if lines else "No activity yet.")

    def _quick_status(self, status: str) -> None:
        if self._selected is None:
            return
        self.contact_status.setCurrentIndex(max(self.contact_status.findData(status), 0))
        self._on_status_changed()

    def schedule_follow_up(self) -> None:
        if self._selected is None:
            return
        dialog = FollowUpDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        updated = self.service.set_follow_up(self._selected, dialog.iso_value())
        self._selected = updated
        self.model.update_row(updated)
        self._show_lead(updated)
        self._refresh_secondary()

    def add_activity(self) -> None:
        if self._selected is None:
            return
        dialog = ActivityDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        updated, _activity = self.service.add_activity(
            self._selected,
            str(dialog.activity_type.currentData()),
            note=dialog.note.toPlainText(),
            contact_method=str(dialog.method.currentData() or ""),
            outcome=str(dialog.outcome.currentData() or ""),
        )
        self._selected = updated
        self.model.update_row(updated)
        self._show_lead(updated)
        self._refresh_secondary()

    def start_sales_prep(self) -> None:
        if self._selected is None:
            QMessageBox.information(
                self,
                "AI Sales Prep",
                "Select a prospect first. Generation is never run for the whole list.",
            )
            return
        if self._prep_worker and self._prep_worker.isRunning():
            return
        self.sales_prep.generate_count += 1
        self.sales_prep.set_busy(True)
        self._refresh_ai_status()
        self._prep_worker = SalesPrepWorker(
            self.service,
            self._selected,
            language=self.sales_prep.language_value(),
            model=self.sales_prep.model_value(),
            parent=self,
        )
        self._prep_worker.succeeded.connect(self._on_sales_prep_done)
        self._prep_worker.failed.connect(self._on_sales_prep_failed)
        self._prep_worker.start()

    def _on_sales_prep_done(self, result: SalesPrepResult) -> None:
        if self._selected is not None:
            self._prep_cache[self._selected.lead.place_id] = result
        self.sales_prep.show_result(result)
        self.statusBar().showMessage("Sales prep ready. Review before any contact.")

    def _on_sales_prep_failed(self, message: str) -> None:
        self.sales_prep.show_error(message)

    def _copy_opener(self) -> None:
        self.sales_prep.copy_text(self.sales_prep.opener.toPlainText())

    def _copy_talking_points(self) -> None:
        self.sales_prep.copy_text(self.sales_prep.points.toPlainText())

    def _copy_full_prep(self) -> None:
        self.sales_prep.copy_text(self.sales_prep.current_full_text())

    def _save_sales_prep_notes(self) -> None:
        if self._selected is None or self.sales_prep.result is None:
            return
        result = self.sales_prep.result
        result.opening_message = self.sales_prep.opener.toPlainText()
        updated = self.service.save_sales_prep(self._selected, result)
        self._selected = updated
        self.model.update_row(updated)
        self._show_lead(updated)
        self.statusBar().showMessage("Saved sales prep to notes.")

    def _open_website(self) -> None:
        if self._selected and self._selected.lead.website:
            QDesktopServices.openUrl(QUrl(self._selected.lead.website))

    def _open_maps(self) -> None:
        if self._selected and self._selected.lead.google_maps_url:
            QDesktopServices.openUrl(QUrl(self._selected.lead.google_maps_url))

    def _refresh_secondary(self) -> None:
        self.pipeline_page.set_leads(self.model.leads())
        self.prospects_page.set_states(self.service.prospects())
        self.dashboard_page.refresh(
            self.service.dashboard(),
            self.service.conversion_summary(),
            self.service.search_history(),
        )

    def _select_place(self, place_id: str) -> None:
        for item in self.model.leads():
            if item.lead.place_id == place_id:
                self._show_lead(item)
                self.tabs.setCurrentIndex(0)
                return

    def _on_pipeline_drop(self, place_id: str, status: str) -> None:
        item = next((row for row in self.model.leads() if row.lead.place_id == place_id), None)
        if item is None:
            return
        updated = self.service.set_status(item, status)
        self.model.update_row(updated)
        if self._selected and self._selected.lead.place_id == place_id:
            self._show_lead(updated)
        self._refresh_secondary()

    def _table_menu(self, pos) -> None:
        if self._selected is None:
            return
        menu = QMenu(self)
        menu.addAction("Mark contacted", lambda: self._quick_status(ContactStatus.CONTACTED.value))
        menu.addAction(
            "Mark interested",
            lambda: self._quick_status(ContactStatus.INTERESTED.value),
        )
        menu.addAction("Schedule follow-up", self.schedule_follow_up)
        menu.addAction("Add activity", self.add_activity)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def export_pipeline(self) -> None:
        items = self.model.leads()
        if not items:
            QMessageBox.information(self, "Export", "There are no leads to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export pipeline", str(Path.home() / "pipeline.csv"), "*.csv"
        )
        if not path:
            return
        written = self.service.export_pipeline(items, Path(path))
        activities = self.service.export_activities(
            [item.lead.place_id for item in items],
            Path(path).with_suffix(".activities.json"),
        )
        QMessageBox.information(
            self, "Export", f"Saved pipeline to:\n{written}\n\nActivities:\n{activities}"
        )

    def backup_db(self) -> None:
        suggested = str(Path.home() / "leadfinder-backup.db")
        path, _ = QFileDialog.getSaveFileName(self, "Backup local data", suggested, "*.db")
        if not path:
            return
        try:
            written = self.service.backup(Path(path))
        except LeadFinderError as error:
            QMessageBox.warning(self, "Backup", friendly_error(error))
            return
        QMessageBox.information(self, "Backup", f"Saved local database to:\n{written}")

    def export_leads(self, fmt: str) -> None:
        if self.export_visible.isChecked():
            leads = []
            for row in range(self.proxy.rowCount()):
                item = self.proxy.lead_from_proxy(row)
                if item is not None:
                    leads.append(item.lead)
        else:
            leads = [item.lead for item in self.model.leads()]
        if not leads:
            QMessageBox.information(self, "Export", "There are no leads to export.")
            return
        suggested = str(Path.home() / f"leads.{fmt}")
        path, _ = QFileDialog.getSaveFileName(self, "Export leads", suggested, f"*.{fmt}")
        if not path:
            return
        try:
            written = self.service.export(leads, fmt=fmt, output=Path(path))
        except LeadFinderError as error:
            QMessageBox.warning(self, "Export", friendly_error(error))
            return
        self.statusBar().showMessage(f"Exported {len(leads)} leads to {written}")
        QMessageBox.information(self, "Export", f"Saved {len(leads)} leads to:\n{written}")

    def _restore_settings(self) -> None:
        self.location.setText(str(self.settings.value("location", "Mar del Plata")))
        self.region.setText(str(self.settings.value("region", "Buenos Aires")))
        self.country.setText(str(self.settings.value("country", "AR")))
        preset = str(self.settings.value("preset", "cafe"))
        index = self.preset.findData(preset)
        if index >= 0:
            self.preset.setCurrentIndex(index)
        self.coverage.setCurrentText(str(self.settings.value("coverage", "budget")))
        self.fields.setCurrentText(str(self.settings.value("fields", "enterprise")))
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        language = str(self.settings.value("ai_output_language", DEFAULT_OUTPUT_LANGUAGE))
        lang_index = self.sales_prep.language.findData(language)
        if lang_index >= 0:
            self.sales_prep.language.setCurrentIndex(lang_index)
        self.sales_prep.model.setText(str(self.settings.value("ai_model", "")))
        self._refresh_ai_status()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_notes()
        self.settings.setValue("location", self.location.text())
        self.settings.setValue("region", self.region.text())
        self.settings.setValue("country", self.country.text())
        self.settings.setValue("preset", self.preset.currentData())
        self.settings.setValue("coverage", self.coverage.currentText())
        self.settings.setValue("fields", self.fields.currentText())
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("ai_output_language", self.sales_prep.language_value())
        self.settings.setValue("ai_model", self.sales_prep.model_value())
        if self._prep_worker and self._prep_worker.isRunning():
            self._prep_worker.wait(2000)
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(2000)
        event.accept()
