from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from leadfinder.ai.models import DEFAULT_OUTPUT_LANGUAGE, SalesPrepResult
from leadfinder.ai.provider import ai_configured, groq_model
from leadfinder.analytics import compare_reports
from leadfinder.application.service import LeadService, friendly_error
from leadfinder.config import SearchConfig
from leadfinder.duplicates import duplicate_hint_text
from leadfinder.errors import ConfigError, LeadFinderError, MissingApiKeyError, UndoError
from leadfinder.gui.analytics_page import AnalyticsPage, custom_bounds, export_report_dialog
from leadfinder.gui.compare_dialog import MAX_COMPARE, CompareDialog, compare_rows
from leadfinder.gui.dashboard_page import DashboardPage
from leadfinder.gui.dialogs import (
    ActivityDialog,
    CampaignDialog,
    ExperimentDialog,
    FollowUpDialog,
    TemplateDialog,
)
from leadfinder.gui.experiments_page import ExperimentsPage
from leadfinder.gui.filter_bar import FilterBar
from leadfinder.gui.formatters import format_when
from leadfinder.gui.insights_page import InsightsPage
from leadfinder.gui.lead_details import LeadDetailsPanel
from leadfinder.gui.lead_model import (
    OPPORTUNITY_LABELS,
    WEBSITE_LABELS,
    LeadFilterProxy,
    LeadTableModel,
)
from leadfinder.gui.pipeline_page import PipelinePage
from leadfinder.gui.prospects_page import ProspectsPage
from leadfinder.gui.saved_filters import (
    all_named_filters,
    filters_for_workspace,
    filters_from_workspace,
    load_custom_filters,
    merge_imported_filters,
    store_custom_filters,
)
from leadfinder.gui.search_panel import SearchPanel
from leadfinder.gui.workers import AnalyzeWorker, InsightsWorker, SalesPrepWorker, SearchWorker
from leadfinder.insights import SegmentInsight
from leadfinder.models import (
    CONTACT_STATUS_LABELS,
    ManagedLead,
    SearchPlan,
    SearchProgress,
    SearchReport,
)
from leadfinder.templates import render_template, values_from_lead
from leadfinder.workflow import ACTIVITY_TYPE_LABELS, ContactStatus


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: LeadService | None = None,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("LeadFinder")
        self.resize(1280, 720)
        self.service = service or LeadService()
        self.settings = settings or QSettings("LeadFinder", "LeadFinder")
        self._worker: SearchWorker | AnalyzeWorker | None = None
        self._prep_worker: SalesPrepWorker | None = None
        self._insights_worker: InsightsWorker | None = None
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
        self._sync_workspace_chrome()

    def _bind_search_panel(self, panel: SearchPanel) -> None:
        self.preset = panel.preset
        self.location = panel.location
        self.region = panel.region
        self.country = panel.country
        self.coverage = panel.coverage
        self.fields = panel.fields
        self.max_requests = panel.max_requests
        self.pages = panel.pages
        self.analyze = panel.analyze
        self.only_no_website = panel.only_no_website
        self.dry_run_btn = panel.dry_run_btn
        self.search_btn = panel.search_btn
        self.cancel_btn = panel.cancel_btn
        self.export_csv_btn = panel.export_csv_btn
        self.export_json_btn = panel.export_json_btn
        self.export_visible = panel.export_visible
        self.analyze_now_btn = panel.analyze_now_btn
        self.export_pipeline_btn = panel.export_pipeline_btn
        self.campaign = panel.campaign
        self.new_campaign_btn = panel.new_campaign_btn
        self.cost_preview = panel.cost_preview
        self.ai_status = panel.ai_status
        self.summary = panel.summary
        self.progress = panel.progress
        self.progress_label = panel.progress_label
        self.counters = panel.counters

    def _bind_filter_bar(self, bar: FilterBar) -> None:
        self.filter_text = bar.filter_text
        self.min_score = bar.min_score
        self.filter_no_website = bar.filter_no_website
        self.filter_phone = bar.filter_phone
        self.filter_operational = bar.filter_operational
        self.filter_status = bar.filter_status
        self.filter_opportunity = bar.filter_opportunity
        self.filter_presence = bar.filter_presence
        self.filter_follow = bar.filter_follow
        self.filter_priority = bar.filter_priority
        self.filter_tag = bar.filter_tag
        self.saved_filters = bar.saved_filters
        self.save_filter_btn = bar.save_filter_btn
        self.compare_btn = bar.compare_btn

    def _bind_details(self, panel: LeadDetailsPanel) -> None:
        self.detail_name = panel.detail_name
        self.detail_score = panel.detail_score
        self.detail_reason = panel.detail_reason
        self.detail_presence = panel.detail_presence
        self.detail_meta = panel.detail_meta
        self.detail_seen = panel.detail_seen
        self.detail_duplicate = panel.detail_duplicate
        self.open_maps = panel.open_maps
        self.open_website = panel.open_website
        self.mark_contacted_btn = panel.mark_contacted_btn
        self.mark_interested_btn = panel.mark_interested_btn
        self.schedule_btn = panel.schedule_btn
        self.activity_btn = panel.activity_btn
        self.undo_btn = panel.undo_btn
        self.copy_phone_btn = panel.copy_phone_btn
        self.copy_pitch_btn = panel.copy_pitch_btn
        self.contact_status = panel.contact_status
        self.manual_priority = panel.manual_priority
        self.notes = panel.notes
        self.tags_edit = panel.tags_edit
        self.follow_label = panel.follow_label
        self.detail_activity = panel.detail_activity
        self.sales_prep = panel.sales_prep
        self.pitch = panel.sales_prep.pitch
        self.detail_tabs = panel.detail_tabs

    def _build_ui(self) -> None:
        header = QLabel("LeadFinder")
        header.setObjectName("title")
        subtitle = QLabel("Discover → Qualify → Track → Analyze → Improve")
        subtitle.setObjectName("hint")
        self.demo_banner = QLabel(
            "DEMO MODE — synthetic data only. These are not real businesses."
        )
        self.demo_banner.setObjectName("demoBanner")
        self.demo_banner.setWordWrap(True)
        self.demo_banner.setVisible(False)

        self.search_panel = SearchPanel()
        self._bind_search_panel(self.search_panel)
        self.filter_bar = FilterBar()
        self._bind_filter_bar(self.filter_bar)
        self.details_panel = LeadDetailsPanel()
        self._bind_details(self.details_panel)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        table_header = self.table.horizontalHeader()
        table_header.setStretchLastSection(True)
        table_header.setSectionsMovable(True)
        self.table.setColumnWidth(1, 180)
        self.empty = QLabel(
            "No leads yet.\n\nConfigure a business search and run Dry Run or Search."
        )
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        table_wrap = QWidget()
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.filter_bar)
        table_layout.addWidget(self.table)
        table_layout.addWidget(self.empty)

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.addWidget(table_wrap)
        right_split.addWidget(self.details_panel)
        right_split.setStretchFactor(0, 3)
        right_split.setStretchFactor(1, 2)

        split = QSplitter()
        split.addWidget(self.search_panel)
        split.addWidget(right_split)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([340, 940])

        self.pipeline_page = PipelinePage()
        self.prospects_page = ProspectsPage()
        self.dashboard_page = DashboardPage()
        self.analytics_page = AnalyticsPage()
        self.insights_page = InsightsPage()
        self.experiments_page = ExperimentsPage()
        self.learn_tabs = QTabWidget()
        self.learn_tabs.addTab(self.analytics_page, "Analytics")
        self.learn_tabs.addTab(self.insights_page, "Insights")
        self.learn_tabs.addTab(self.experiments_page, "Experiments")
        self.tabs = QTabWidget()
        self.tabs.addTab(split, "Search")
        self.tabs.addTab(self.pipeline_page, "Pipeline")
        self.tabs.addTab(self.prospects_page, "Prospects")
        self.tabs.addTab(self.dashboard_page, "Dashboard")
        self.tabs.addTab(self.learn_tabs, "Learn")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addWidget(self.demo_banner)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")
        self.workspace_label = QLabel("My Workspace")
        self.statusBar().addPermanentWidget(self.workspace_label)
        self.status_undo_btn = QPushButton("Undo")
        self.status_undo_btn.setVisible(False)
        self.statusBar().addPermanentWidget(self.status_undo_btn)

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
        backup_action = QAction("Backup data", self)
        backup_action.triggered.connect(self.backup_db)
        self.addAction(backup_action)
        restore_action = QAction("Restore data", self)
        restore_action.triggered.connect(self.restore_db)
        export_ws_action = QAction("Export local workspace", self)
        export_ws_action.triggered.connect(self.export_workspace)
        import_ws_action = QAction("Import workspace (merge)", self)
        import_ws_action.triggered.connect(self.import_workspace)
        doctor_action = QAction("Doctor", self)
        doctor_action.triggered.connect(self.show_doctor)
        settings_action = QAction("Settings", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        self.addAction(settings_action)
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        data_folder_action = QAction("Open data folder", self)
        data_folder_action.triggered.connect(self.open_data_folder)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(export_action)
        file_menu.addAction(backup_action)
        file_menu.addAction(restore_action)
        file_menu.addAction(export_ws_action)
        file_menu.addAction(import_ws_action)
        file_menu.addAction(data_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(doctor_action)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        demo_menu = self.menuBar().addMenu("Demo")
        enter_demo = QAction("Try Demo Mode", self)
        enter_demo.triggered.connect(self.enter_demo_mode)
        reset_demo = QAction("Reset Demo Data", self)
        reset_demo.triggered.connect(self.reset_demo_data)
        exit_demo = QAction("Return to My Workspace", self)
        exit_demo.triggered.connect(self.exit_demo_mode)
        demo_menu.addAction(enter_demo)
        demo_menu.addAction(reset_demo)
        demo_menu.addAction(exit_demo)

        help_menu = self.menuBar().addMenu("Help")
        welcome_action = QAction("Show Welcome", self)
        welcome_action.setShortcut(QKeySequence("F1"))
        welcome_action.triggered.connect(self.show_welcome)
        about_action = QAction("About LeadFinder", self)
        about_action.triggered.connect(self.open_about)
        diagnostics_action = QAction("Copy diagnostics", self)
        diagnostics_action.triggered.connect(self.copy_diagnostics)
        help_menu.addAction(welcome_action)
        help_menu.addAction(diagnostics_action)
        help_menu.addAction(about_action)
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
        self.filter_priority.currentIndexChanged.connect(self._apply_filters)
        self.filter_tag.textChanged.connect(self._apply_filters)
        self.saved_filters.currentIndexChanged.connect(self._apply_saved_filter)
        self.save_filter_btn.clicked.connect(self._save_current_filter)
        self.compare_btn.clicked.connect(self.compare_selected)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self.table.customContextMenuRequested.connect(self._table_menu)
        self.contact_status.currentIndexChanged.connect(self._on_status_changed)
        self.manual_priority.currentIndexChanged.connect(self._on_priority_changed)
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
        self.undo_btn.clicked.connect(self.undo_last)
        self.status_undo_btn.clicked.connect(self.undo_last)
        self.copy_phone_btn.clicked.connect(self._copy_phone)
        self.copy_pitch_btn.clicked.connect(self._copy_pitch)
        self.pitch.selector.currentIndexChanged.connect(self._render_pitch)
        self.pitch.copy_btn.clicked.connect(self._copy_pitch)
        self.pitch.new_btn.clicked.connect(self._new_template)
        self.pitch.edit_btn.clicked.connect(self._edit_template)
        self.pitch.delete_btn.clicked.connect(self._delete_template)
        self.tabs.currentChanged.connect(self._refresh_secondary)
        self.pipeline_page.status_dropped.connect(self._on_pipeline_drop)
        self.pipeline_page.card_selected.connect(self._select_place)
        self.prospects_page.selected.connect(self._select_place)
        self.new_campaign_btn.clicked.connect(self.create_campaign)
        self.analytics_page.refresh_btn.clicked.connect(self._refresh_analytics)
        self.analytics_page.export_btn.clicked.connect(self.export_analytics)
        self.analytics_page.period.currentIndexChanged.connect(self._refresh_analytics)
        self.analytics_page.campaign.currentIndexChanged.connect(self._refresh_analytics)
        self.sales_prep.generate_btn.clicked.connect(self.start_sales_prep)
        self.sales_prep.regenerate_btn.clicked.connect(self.start_sales_prep)
        self.sales_prep.copy_opener_btn.clicked.connect(self._copy_opener)
        self.sales_prep.copy_points_btn.clicked.connect(self._copy_talking_points)
        self.sales_prep.copy_full_btn.clicked.connect(self._copy_full_prep)
        self.sales_prep.save_notes_btn.clicked.connect(self._save_sales_prep_notes)
        self.insights_page.refresh_btn.clicked.connect(self._refresh_insights)
        self.insights_page.export_btn.clicked.connect(self.export_insights)
        self.insights_page.explain_requested.connect(self.explain_insights)
        self.insights_page.create_experiment_requested.connect(self.create_experiment_from_insight)
        self.insights_page.period.currentIndexChanged.connect(self._refresh_insights)
        self.insights_page.campaign.currentIndexChanged.connect(self._refresh_insights)
        self.experiments_page.refresh_requested.connect(self._refresh_experiments)
        self.experiments_page.save_notes_requested.connect(self._save_experiment)
        self.experiments_page.summarize_requested.connect(self.summarize_experiment)
        self.preset.currentIndexChanged.connect(self._update_cost_preview)
        self.coverage.currentIndexChanged.connect(self._update_cost_preview)
        self.fields.currentIndexChanged.connect(self._update_cost_preview)
        self.pages.valueChanged.connect(self._update_cost_preview)
        self.max_requests.valueChanged.connect(self._update_cost_preview)
        self.location.editingFinished.connect(self._update_cost_preview)

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
        self._update_cost_preview()
        self.statusBar().showMessage("Dry run complete. No API requests were made.")

    def _plan_text(self, plan: SearchPlan) -> str:
        from leadfinder.costs.estimator import estimate_plan, page_scenarios
        from leadfinder.costs.models import format_estimate

        locations = "\n".join(f"  - {item}" for item in plan.locations[:40])
        extra = "" if len(plan.locations) <= 40 else f"\n  … {len(plan.locations) - 40} more"
        estimate = estimate_plan(plan)
        scenario_lines = []
        for pages, requests, cost in page_scenarios(
            query_count=plan.max_queries,
            max_requests=self.max_requests.value(),
            field_profile=plan.field_profile,
        ):
            scenario_lines.append(
                f"  {pages} page(s): {requests} requests · {format_estimate(cost)}"
            )
        return (
            f"Business: {plan.business}\n"
            f"Location: {', '.join(plan.locations[:8]) or '(none)'}\n"
            f"Coverage: {plan.coverage}\n"
            f"Estimated search requests: {plan.max_api_requests}\n"
            f"Max pages: {plan.pages}\n"
            f"Field profile: {plan.field_profile}\n"
            f"{format_estimate(estimate)}\n"
            f"Page comparison (no network):\n" + "\n".join(scenario_lines) + "\n\n"
            f"Search terms: {', '.join(plan.search_terms)}\n"
            f"Country: {plan.country}\n"
            f"Region: {plan.region or '(none)'}\n"
            f"Max queries: {plan.max_queries}\n"
            f"Page size: {plan.page_size}\n"
            f"Billing tier: {plan.billing_tier}\n"
            f"Website analysis: {'yes' if plan.analyze_websites else 'no'}\n\n"
            f"Locations:\n{locations}{extra}\n\n"
            "No API requests were made."
        )

    def start_search(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if self._is_demo_workspace():
            switch = QMessageBox.question(
                self,
                "Demo Mode",
                "Google Places search runs against My Workspace, not Demo Mode.\n\n"
                "Switch to My Workspace now? Demo data will stay on disk.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if switch != QMessageBox.StandardButton.Yes:
                return
            self.exit_demo_mode()
            return
        if not self._confirm_places_cost_notice():
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
        self._worker = SearchWorker(
            self.service,
            self.current_config(),
            campaign_id=self._selected_campaign_id(),
            parent=self,
        )
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
        from leadfinder.costs.estimator import estimate_requests
        from leadfinder.costs.models import format_estimate

        estimate = estimate_requests(report.api_requests, self.fields.currentText())
        cancelled = " (cancelled)" if report.cancelled else ""
        self.summary.setPlainText(
            f"This search\n"
            f"Requests: {report.api_requests}\n"
            f"{format_estimate(estimate)}\n\n"
            f"Queries: {report.queries_executed}\n"
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
            manual_priority=str(self.filter_priority.currentData() or ""),
        )
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        has_rows = self.proxy.rowCount() > 0
        self.table.setVisible(has_rows or self.model.rowCount() > 0)
        self.empty.setVisible(self.model.rowCount() == 0)

    def _on_selection(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        self.compare_btn.setEnabled(2 <= len(indexes) <= MAX_COMPARE)
        if not indexes:
            return
        item = self.proxy.lead_from_proxy(indexes[-1].row())
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
        hint = duplicate_hint_text(item, self.model.leads(), self.service.store.list_all())
        self.detail_duplicate.setText(hint)
        self.detail_duplicate.setVisible(bool(hint))
        self.copy_phone_btn.setEnabled(bool(lead.phone))
        self._sync_undo(item)
        self._render_pitch()
        self.follow_label.setText(format_when(item.next_follow_up_at))
        self.tags_edit.setText(item.tags)
        self.open_maps.setEnabled(bool(lead.google_maps_url))
        self.open_website.setEnabled(bool(lead.website))
        index = self.contact_status.findData(item.contact_status)
        self.contact_status.setCurrentIndex(max(index, 0))
        p_index = self.manual_priority.findData(item.manual_priority or "normal")
        self.manual_priority.setCurrentIndex(max(p_index, 0))
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
        label = CONTACT_STATUS_LABELS.get(status, status)
        self._offer_undo(f"Status changed to {label}")

    def _on_priority_changed(self) -> None:
        if self._updating_details or self._selected is None:
            return
        priority = str(self.manual_priority.currentData() or "normal")
        updated = self.service.set_priority(self._selected, priority)
        self._selected = updated
        self.model.update_row(updated)
        self._show_lead(updated)
        self._offer_undo("Priority updated")

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
        self._offer_undo("Follow-up updated")

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
            template_body=self.pitch.current_template_body(),
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
        self._refresh_campaigns()
        self._refresh_analytics()
        self._refresh_insights()
        self._refresh_experiments()

    def _refresh_campaigns(self) -> None:
        campaigns = self.service.campaigns()
        current = self.campaign.currentData()
        self.campaign.blockSignals(True)
        self.campaign.clear()
        self.campaign.addItem("Auto (same-day search)", 0)
        for campaign in campaigns:
            self.campaign.addItem(campaign.name, campaign.id)
        index = self.campaign.findData(current)
        self.campaign.setCurrentIndex(max(index, 0))
        self.campaign.blockSignals(False)
        self.analytics_page.fill_campaigns(campaigns)
        self.insights_page.fill_campaigns(campaigns)

    def _selected_campaign_id(self) -> int | None:
        value = self.campaign.currentData()
        if not value:
            return None
        return int(value)

    def create_campaign(self) -> None:
        dialog = CampaignDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        name = dialog.name.text().strip()
        if not name:
            return
        created = self.service.create_campaign(
            name=name,
            business_preset=dialog.preset.text().strip(),
            location=dialog.location.text().strip(),
            region=dialog.region.text().strip(),
            country=dialog.country.text().strip().upper(),
            notes=dialog.notes.toPlainText(),
        )
        self._refresh_campaigns()
        index = self.campaign.findData(created.id)
        if index >= 0:
            self.campaign.setCurrentIndex(index)

    def _analytics_period(self):
        choice = int(self.analytics_page.period.currentData() or 30)
        if choice == -1:
            start, end = custom_bounds(self.analytics_page)
            return self.service.analytics_period(days=None, start=start, end=end)
        if choice == 0:
            return self.service.analytics_period(days=None)
        return self.service.analytics_period(days=choice)

    def _refresh_analytics(self) -> None:
        period = self._analytics_period()
        campaign_id = self.analytics_page.selected_campaign_id()
        report = self.service.analytics_report(period, campaign_id=campaign_id)
        comparison = ""
        left_id = self.analytics_page.compare_a.currentData()
        right_id = self.analytics_page.compare_b.currentData()
        if left_id and right_id and left_id != right_id:
            left = self.service.analytics_report(period, campaign_id=int(left_id))
            right = self.service.analytics_report(period, campaign_id=int(right_id))
            lines = [f"{left.campaign_name}  vs  {right.campaign_name}", "Metric | A | B"]
            for metric, a_val, b_val in compare_reports(left, right):
                lines.append(f"{metric} | {a_val} | {b_val}")
            comparison = "\n".join(lines)
        cost_text = self.service.campaign_cost_text(campaign_id, report)
        self.analytics_page.show_report(report, comparison, cost_text)

    def _insights_period(self):
        choice = int(self.insights_page.period.currentData() or 30)
        if choice == 0:
            return self.service.analytics_period(days=None)
        return self.service.analytics_period(days=choice)

    def _refresh_insights(self) -> None:
        period = self._insights_period()
        campaign_id = self.insights_page.selected_campaign_id()
        report = self.service.insights_report(period, campaign_id=campaign_id)
        self.insights_page.show_report(report)

    def export_insights(self) -> None:
        period = self._insights_period()
        report = self.service.insights_report(
            period, campaign_id=self.insights_page.selected_campaign_id()
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export insights",
            str(Path.home() / "insights.md"),
            "Markdown (*.md);;JSON (*.json)",
        )
        if not path:
            return
        written = self.service.export_insights(report, Path(path))
        QMessageBox.information(self, "Export", f"Saved insights to:\n{written}")

    def explain_insights(self) -> None:
        period = self._insights_period()
        report = self.service.insights_report(
            period, campaign_id=self.insights_page.selected_campaign_id()
        )
        self._start_insights_worker(report, experiment=False)

    def _start_insights_worker(self, source: object, *, experiment: bool) -> None:
        if self._insights_worker and self._insights_worker.isRunning():
            return
        language = self.sales_prep.language_value()
        self._insights_worker = InsightsWorker(
            self.service, source, language=language, experiment=experiment, parent=self
        )
        self._insights_worker.succeeded.connect(self._on_insights_ready)
        self._insights_worker.failed.connect(self._on_insights_failed)
        self._insights_worker.start()
        self.statusBar().showMessage("Explaining aggregated metrics...")

    def _on_insights_ready(self, result) -> None:
        observed = "\n".join(f"- {item}" for item in result.observed)
        hypotheses = "\n".join(f"- {item}" for item in result.hypotheses)
        experiments = "\n".join(f"- {item}" for item in result.experiments)
        cautions = "\n".join(f"- {item}" for item in result.cautions)
        text = (
            f"{result.summary}\n\nObserved\n{observed}\n\n"
            f"Hypothesis\n{hypotheses}\n\nExperiments\n{experiments}\n\n"
            f"Cautions\n{cautions}"
        )
        self.insights_page.show_explanation(text)
        self.statusBar().showMessage("AI explanation ready (aggregated metrics only).")

    def _on_insights_failed(self, message: str) -> None:
        self.insights_page.show_explanation(message)
        QMessageBox.warning(self, "AI", message)

    def create_experiment_from_insight(self, insight: SegmentInsight) -> None:
        from leadfinder.workspace import criteria_from_insight

        criteria = criteria_from_insight(insight.dimension, insight.key)
        dialog = ExperimentDialog(
            self,
            name=f"Try {insight.label}",
            hypothesis=(
                f"Businesses matching {insight.label} may show different "
                "contact->interest than the overall baseline."
            ),
            business_preset=criteria.get("business_preset", ""),
            location=criteria.get("location", ""),
            digital_presence=criteria.get("digital_presence", ""),
            opportunity_level=criteria.get("opportunity_level", ""),
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        name = dialog.name.text().strip()
        if not name:
            return
        self.service.create_experiment(
            name=name,
            hypothesis=dialog.hypothesis.toPlainText().strip(),
            business_preset=dialog.preset.text().strip(),
            location=dialog.location.text().strip(),
            digital_presence=dialog.presence.text().strip(),
            opportunity_level=dialog.opportunity.text().strip(),
            campaign_ids=(
                [cid] if (cid := self.insights_page.selected_campaign_id()) else None
            ),
        )
        self.learn_tabs.setCurrentWidget(self.experiments_page)
        self._refresh_experiments()
        QMessageBox.information(
            self,
            "Experiment",
            "Experiment saved as a draft. Review it, then run a search yourself. "
            "LeadFinder did not start a search.",
        )

    def _refresh_experiments(self) -> None:
        experiments = self.service.experiments()
        metrics = [
            self.service.experiment_metrics(item, days=0) for item in experiments
        ]
        self.experiments_page.show_experiments(experiments, metrics)

    def _save_experiment(self, experiment) -> None:
        self.service.update_experiment(
            experiment.id,
            status=experiment.status,
            observations=experiment.observations,
            notes=experiment.notes,
            conclusion=experiment.conclusion,
        )
        self._refresh_experiments()
        self.statusBar().showMessage("Experiment notes saved.")

    def summarize_experiment(self, metrics) -> None:
        self._start_insights_worker(metrics, experiment=True)

    def _update_cost_preview(self) -> None:
        from leadfinder.costs.models import format_estimate

        try:
            plan, estimate, scenarios = self.service.cost_preview(self.current_config())
        except LeadFinderError as error:
            self.cost_preview.setText(str(error))
            return
        lines = [
            f"{plan.billing_tier}: up to {plan.max_api_requests} API requests "
            f"({plan.max_queries} queries × {plan.pages} page(s)).",
            format_estimate(estimate),
            "Compare pages (no network):",
        ]
        for pages, requests, cost in scenarios:
            lines.append(f"{pages} page(s) → {requests} requests · {format_estimate(cost)}")
        self.cost_preview.setText("\n".join(lines))

    def export_analytics(self) -> None:
        period = self._analytics_period()
        report = self.service.analytics_report(
            period, campaign_id=self.analytics_page.selected_campaign_id()
        )
        export_report_dialog(self, self.service, report)

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
        menu.addAction("Set follow-up", self.schedule_follow_up)
        menu.addAction("Priority high", lambda: self._quick_priority("high"))
        if self._selected.lead.phone:
            menu.addAction("Copy phone", self._copy_phone)
        if self._selected.lead.website:
            menu.addAction("Open website", self._open_website)
        menu.addAction("Copy pitch", self._copy_pitch)
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
        from leadfinder.paths import backup_filename, backups_dir

        suggested = str(backups_dir() / backup_filename(demo=self._is_demo_workspace()))
        path, _ = QFileDialog.getSaveFileName(self, "Backup data", suggested, "*.db")
        if not path:
            return
        try:
            written = self.service.backup(Path(path))
        except LeadFinderError as error:
            QMessageBox.warning(self, "Backup", friendly_error(error))
            return
        QMessageBox.information(self, "Backup", f"Saved local database to:\n{written}")

    def restore_db(self) -> None:
        if self._is_demo_workspace():
            QMessageBox.information(
                self,
                "Restore data",
                "Restore is disabled in Demo Mode so a backup cannot overwrite "
                "this synthetic workspace by accident. Return to My Workspace first.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(self, "Restore data", str(Path.home()), "*.db")
        if not path:
            return
        confirm = QMessageBox.question(
            self,
            "Restore data",
            "This replaces the current local database after saving a safety backup.\n\nContinue?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            safety = self.service.restore(Path(path))
        except LeadFinderError as error:
            QMessageBox.warning(self, "Restore", friendly_error(error))
            return
        QMessageBox.information(
            self,
            "Restore",
            f"Restore complete.\nPrevious database saved to:\n{safety}",
        )
        self._refresh_secondary()

    def export_workspace(self) -> None:
        name = (
            "leadfinder-demo-workspace.zip"
            if self._is_demo_workspace()
            else "leadfinder-workspace.zip"
        )
        suggested = str(Path.home() / name)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export local workspace", suggested, "*.zip"
        )
        if not path:
            return
        settings = {
            "location": self.location.text(),
            "region": self.region.text(),
            "country": self.country.text(),
            "preset": self.preset.currentData(),
            "coverage": self.coverage.currentText(),
            "fields": self.fields.currentText(),
            "saved_filters": filters_for_workspace(load_custom_filters(self.settings)),
        }
        try:
            written = self.service.export_workspace(Path(path), settings=settings)
        except LeadFinderError as error:
            QMessageBox.warning(self, "Export", friendly_error(error))
            return
        QMessageBox.information(self, "Export", f"Workspace saved to:\n{written}")

    def import_workspace(self) -> None:
        if self._is_demo_workspace():
            QMessageBox.information(
                self,
                "Import workspace",
                "Import is disabled in Demo Mode so a real workspace cannot merge "
                "into synthetic demo data. Return to My Workspace first.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import workspace", str(Path.home()), "*.zip"
        )
        if not path:
            return
        confirm = QMessageBox.question(
            self,
            "Import workspace",
            "Merge this workspace into the current database by Place ID?\n"
            "Existing leads are kept. New records are added.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            added = self.service.import_workspace(Path(path))
        except LeadFinderError as error:
            QMessageBox.warning(self, "Import", friendly_error(error))
            return
        incoming = filters_from_workspace(added.pop("imported_saved_filters", {}))
        if incoming:
            merged = merge_imported_filters(load_custom_filters(self.settings), incoming)
            store_custom_filters(self.settings, merged)
            self._reload_saved_filter_names()
        self._reload_templates()
        self._refresh_secondary()
        QMessageBox.information(
            self,
            "Import",
            "Merged workspace.\n"
            f"Leads added: {added.get('leads', 0)}\n"
            f"Leads skipped: {added.get('skipped_leads', 0)}\n"
            f"Campaigns: {added.get('campaigns', 0)}\n"
            f"Activities: {added.get('activities', 0)}\n"
            f"Experiments: {added.get('experiments', 0)}\n"
            f"Templates: {added.get('templates', 0)}",
        )

    def show_doctor(self) -> None:
        from leadfinder.doctor import format_doctor

        report = self.service.doctor()
        QMessageBox.information(self, "LeadFinder Doctor", format_doctor(report))

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
        suggested = str(self._export_dir() / f"leads.{fmt}")
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
        stored_fields = str(self.settings.value("fields", "enterprise"))
        if self.fields.findText(stored_fields) >= 0:
            self.fields.setCurrentText(stored_fields)
        from leadfinder.desktop.settings_keys import DEFAULT_MAX_REQUESTS, DEFAULT_PAGES

        self.pages.setValue(self._int_setting(DEFAULT_PAGES, 1, 1, 3))
        self.max_requests.setValue(self._int_setting(DEFAULT_MAX_REQUESTS, 100, 1, 500))
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        language = str(self.settings.value("ai_output_language", DEFAULT_OUTPUT_LANGUAGE))
        lang_index = self.sales_prep.language.findData(language)
        if lang_index >= 0:
            self.sales_prep.language.setCurrentIndex(lang_index)
        self.sales_prep.model.setText(str(self.settings.value("ai_model", "")))
        header_state = self.settings.value("table_header")
        if header_state:
            try:
                self.table.horizontalHeader().restoreState(header_state)
            except (TypeError, ValueError, RuntimeError):
                pass
        self._reload_saved_filter_names()
        self._reload_templates()
        self._refresh_ai_status()
        self._update_cost_preview()

    def _reload_saved_filter_names(self) -> None:
        current = self.saved_filters.currentText()
        self.saved_filters.blockSignals(True)
        self.saved_filters.clear()
        self.saved_filters.addItem("Saved filters…", "")
        for name in all_named_filters(self.settings):
            self.saved_filters.addItem(name, name)
        index = self.saved_filters.findText(current)
        self.saved_filters.setCurrentIndex(max(index, 0))
        self.saved_filters.blockSignals(False)

    def _apply_saved_filter(self) -> None:
        name = str(self.saved_filters.currentData() or "")
        spec = all_named_filters(self.settings).get(name)
        if not spec:
            return
        self.filter_text.setText(str(spec.get("text") or ""))
        self.min_score.setValue(int(spec.get("min_score") or 0))
        self.filter_no_website.setChecked(bool(spec.get("no_website")))
        self.filter_phone.setChecked(bool(spec.get("has_phone")))
        self.filter_operational.setChecked(bool(spec.get("operational", True)))
        self._set_combo(self.filter_status, str(spec.get("status") or ""))
        self._set_combo(self.filter_opportunity, str(spec.get("opportunity") or ""))
        self._set_combo(self.filter_presence, str(spec.get("presence") or ""))
        self._set_combo(self.filter_follow, str(spec.get("follow") or ""))
        self._set_combo(self.filter_priority, str(spec.get("priority") or ""))
        self.filter_tag.setText(str(spec.get("tag") or ""))

    def _set_combo(self, combo, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _current_filter_spec(self) -> dict:
        return {
            "text": self.filter_text.text(),
            "min_score": self.min_score.value(),
            "no_website": self.filter_no_website.isChecked(),
            "has_phone": self.filter_phone.isChecked(),
            "operational": self.filter_operational.isChecked(),
            "status": str(self.filter_status.currentData() or ""),
            "opportunity": str(self.filter_opportunity.currentData() or ""),
            "presence": str(self.filter_presence.currentData() or ""),
            "follow": str(self.filter_follow.currentData() or ""),
            "tag": self.filter_tag.text(),
            "priority": str(self.filter_priority.currentData() or ""),
        }

    def _save_current_filter(self) -> None:
        name, ok = QInputDialog.getText(self, "Save filter", "Filter name")
        if not ok or not name.strip():
            return
        custom = load_custom_filters(self.settings)
        custom[name.strip()] = self._current_filter_spec()
        store_custom_filters(self.settings, custom)
        self._reload_saved_filter_names()
        index = self.saved_filters.findText(name.strip())
        if index >= 0:
            self.saved_filters.setCurrentIndex(index)

    def _offer_undo(self, message: str) -> None:
        can = bool(self._selected and self.service.can_undo(self._selected.lead.place_id))
        self.undo_btn.setEnabled(can)
        self.status_undo_btn.setVisible(can)
        self.statusBar().showMessage(message)

    def _sync_undo(self, item: ManagedLead) -> None:
        can = self.service.can_undo(item.lead.place_id)
        self.undo_btn.setEnabled(can)
        self.status_undo_btn.setVisible(can)

    def undo_last(self) -> None:
        if self._selected is None:
            return
        try:
            updated = self.service.undo_last(self._selected)
        except UndoError as error:
            QMessageBox.information(self, "Undo", str(error))
            self._sync_undo(self._selected)
            return
        self._selected = updated
        self.model.update_row(updated)
        self._show_lead(updated)
        self._refresh_secondary()
        self.statusBar().showMessage("Change undone. Activity history was kept.")

    def _copy_phone(self) -> None:
        if self._selected and self._selected.lead.phone:
            self.sales_prep.copy_text(self._selected.lead.phone)

    def _copy_pitch(self) -> None:
        text = self.pitch.preview.toPlainText().strip()
        if text:
            self.sales_prep.copy_text(text)

    def _render_pitch(self) -> None:
        if self._selected is None:
            self.pitch.preview.setPlainText("")
            return
        body = self.pitch.current_template_body()
        if not body:
            self.pitch.preview.setPlainText("")
            return
        self.pitch.preview.setPlainText(
            render_template(body, values_from_lead(self._selected))
        )

    def _reload_templates(self) -> None:
        keep = self.pitch.selected_id()
        self.pitch.reload(self.service.list_templates(), keep_id=keep)
        self._render_pitch()

    def _new_template(self) -> None:
        dialog = TemplateDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        created = self.service.create_template(
            name=dialog.name.text(),
            body=dialog.body.toPlainText(),
            business_type=dialog.business_type.text(),
            presence_type=dialog.presence_type.text(),
            language=dialog.language.text(),
        )
        self.pitch.reload(self.service.list_templates(), keep_id=created.id)
        self._render_pitch()

    def _edit_template(self) -> None:
        template_id = self.pitch.selected_id()
        if not template_id:
            return
        current = next(
            (item for item in self.service.list_templates() if item.id == template_id),
            None,
        )
        if current is None:
            return
        dialog = TemplateDialog(
            self,
            name=current.name,
            body=current.body,
            business_type=current.business_type,
            presence_type=current.presence_type,
            language=current.language,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.service.update_template(
            template_id,
            name=dialog.name.text(),
            body=dialog.body.toPlainText(),
            business_type=dialog.business_type.text(),
            presence_type=dialog.presence_type.text(),
            language=dialog.language.text(),
        )
        self._reload_templates()

    def _delete_template(self) -> None:
        template_id = self.pitch.selected_id()
        if not template_id:
            return
        self.service.delete_template(template_id)
        self._reload_templates()

    def _quick_priority(self, priority: str) -> None:
        if self._selected is None:
            return
        index = self.manual_priority.findData(priority)
        self.manual_priority.setCurrentIndex(max(index, 0))
        self._on_priority_changed()

    def compare_selected(self) -> None:
        items: list[ManagedLead] = []
        for index in self.table.selectionModel().selectedRows():
            item = self.proxy.lead_from_proxy(index.row())
            if item is not None:
                items.append(item)
        if not (2 <= len(items) <= MAX_COMPARE):
            QMessageBox.information(
                self,
                "Compare selected",
                "Select between 2 and 5 leads to compare.",
            )
            return
        rows = compare_rows(
            items,
            session=self.model.leads(),
            local=self.service.store.list_all(),
        )
        CompareDialog(items, rows, self).exec()

    def _is_demo_workspace(self) -> bool:
        from leadfinder.paths import is_demo_database

        return is_demo_database(self.service.store.path)

    def _sync_workspace_chrome(self) -> None:
        demo = self._is_demo_workspace()
        self.demo_banner.setVisible(demo)
        self.workspace_label.setText("Demo Workspace" if demo else "My Workspace")
        title = "LeadFinder — DEMO MODE" if demo else "LeadFinder"
        self.setWindowTitle(title)
        self.dashboard_page.set_demo_guide(demo)

    def _export_dir(self) -> Path:
        from leadfinder.desktop.settings_keys import DEFAULT_EXPORT_DIR
        from leadfinder.paths import exports_dir

        raw = str(self.settings.value(DEFAULT_EXPORT_DIR, "") or "").strip()
        if raw:
            path = Path(raw)
            path.mkdir(parents=True, exist_ok=True)
            return path
        return exports_dir()

    def _confirm_places_cost_notice(self) -> bool:
        from leadfinder.desktop.settings_keys import PLACES_COST_NOTICE

        if self.settings.value(PLACES_COST_NOTICE, False, type=bool):
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Google Places cost")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("Google Places searches may incur charges.")
        box.setInformativeText(
            "LeadFinder shows estimated list-price cost before searching. "
            "It does not read your Google Cloud invoice."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.button(QMessageBox.StandardButton.Ok).setText("Continue")
        if box.exec() != QMessageBox.StandardButton.Ok:
            return False
        self.settings.setValue(PLACES_COST_NOTICE, True)
        return True

    def _replace_service(self, store_path: Path) -> None:
        from leadfinder.storage.local_leads import LocalLeadStore

        old = self.service.store
        self.service = LeadService(LocalLeadStore(store_path))
        try:
            old.close()
        except Exception:
            pass
        self._prep_cache.clear()
        self._selected = None
        self.model.set_leads([])
        self._update_empty_state()
        self._refresh_secondary()
        self._reload_templates()
        self._sync_workspace_chrome()

    def enter_demo_mode(self) -> None:
        from leadfinder.demo import ensure_demo_database

        if self._is_demo_workspace():
            self.statusBar().showMessage("Already in Demo Mode.")
            return
        path = ensure_demo_database()
        self._replace_service(path)
        self.statusBar().showMessage("Demo Mode — synthetic data only.")

    def exit_demo_mode(self) -> None:
        from leadfinder.paths import data_dir

        if not self._is_demo_workspace():
            self.statusBar().showMessage("Already in My Workspace.")
            return
        self._replace_service(data_dir() / "leadfinder.db")
        self.statusBar().showMessage("Returned to My Workspace.")

    def reset_demo_data(self) -> None:
        from leadfinder.demo import ensure_demo_database
        from leadfinder.paths import demo_db_path

        if not self._is_demo_workspace():
            QMessageBox.information(
                self,
                "Reset Demo Data",
                "Switch to Demo Mode first. Reset never touches My Workspace.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Reset Demo Data",
            "Replace the demo database with a fresh synthetic set?\n\n"
            "My Workspace will not be changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.store.close()
        except Exception:
            pass
        ensure_demo_database(reset=True)
        self._replace_service(demo_db_path())
        self.statusBar().showMessage("Demo data was reset.")

    def open_settings(self) -> None:
        from leadfinder.gui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self._restore_settings()
            self._refresh_ai_status()

    def open_about(self) -> None:
        from leadfinder.gui.about_dialog import AboutDialog

        AboutDialog(self).exec()

    def open_data_folder(self) -> None:
        from leadfinder.paths import data_dir

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))

    def copy_diagnostics(self) -> None:
        from PySide6.QtGui import QGuiApplication

        from leadfinder.desktop.diagnostics import collect_diagnostics

        text = collect_diagnostics(db_path=self.service.store.path)
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self.statusBar().showMessage("Diagnostics copied. Keys and lead data are not included.")

    def show_welcome(self) -> None:
        from leadfinder.gui.onboarding import run_onboarding

        dialog = run_onboarding(self, self.settings)
        if dialog.result() != dialog.DialogCode.Accepted:
            return
        if dialog.choice == "demo":
            self.enter_demo_mode()
        elif dialog.choice == "import" and dialog.import_path is not None:
            if self._is_demo_workspace():
                self.exit_demo_mode()
            try:
                added = self.service.import_workspace(dialog.import_path)
            except LeadFinderError as error:
                QMessageBox.warning(self, "Import workspace", friendly_error(error))
                return
            self._refresh_secondary()
            QMessageBox.information(
                self,
                "Import workspace",
                f"Merged workspace. Leads: {added.get('leads', 0)}",
            )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_notes()
        self.settings.setValue("location", self.location.text())
        self.settings.setValue("region", self.region.text())
        self.settings.setValue("country", self.country.text())
        self.settings.setValue("preset", self.preset.currentData())
        self.settings.setValue("coverage", self.coverage.currentText())
        self.settings.setValue("fields", self.fields.currentText())
        from leadfinder.desktop.settings_keys import DEFAULT_MAX_REQUESTS, DEFAULT_PAGES

        self.settings.setValue(DEFAULT_PAGES, self.pages.value())
        self.settings.setValue(DEFAULT_MAX_REQUESTS, self.max_requests.value())
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("ai_output_language", self.sales_prep.language_value())
        self.settings.setValue("ai_model", self.sales_prep.model_value())
        self.settings.setValue("table_header", self.table.horizontalHeader().saveState())
        if self._prep_worker and self._prep_worker.isRunning():
            self._prep_worker.wait(2000)
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(2000)
        event.accept()

    def _int_setting(self, key: str, default: int, lo: int, hi: int) -> int:
        raw = self.settings.value(key, default)
        try:
            value = int(str(raw))
        except (TypeError, ValueError):
            value = default
        return max(lo, min(hi, value))
