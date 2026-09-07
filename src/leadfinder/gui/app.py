from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

from leadfinder.errors import DatabaseError, GuiDependencyError, RestoreError


def run_gui(*, show_onboarding: bool | None = None) -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError as error:
        raise GuiDependencyError(
            "GUI dependencies are not installed.\n\n"
            'Install them with:\n\n    pip install -e ".[gui]"'
        ) from error

    from leadfinder.application.service import LeadService
    from leadfinder.desktop.assets import bundled_icon_path
    from leadfinder.desktop.identity import apply_qt_identity
    from leadfinder.desktop.runtime import smoke_exit_requested
    from leadfinder.gui.main_window import MainWindow
    from leadfinder.gui.styles import LIGHT_QSS
    from leadfinder.logging_setup import configure_logging
    from leadfinder.storage.local_leads import LocalLeadStore

    configure_logging()
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv)
    apply_qt_identity(app)
    app.setStyle("Fusion")
    app.setStyleSheet(LIGHT_QSS)
    icon_file = bundled_icon_path()
    if icon_file.is_file():
        app.setWindowIcon(QIcon(str(icon_file)))

    smoke = smoke_exit_requested()
    smoke_dir: tempfile.TemporaryDirectory[str] | None = None
    db_path: Path | None = None
    if smoke:
        smoke_dir = tempfile.TemporaryDirectory(prefix="leadfinder-smoke-")
        db_path = Path(smoke_dir.name) / "smoke.db"

    window: MainWindow | None = None
    try:
        store = LocalLeadStore(db_path) if db_path is not None else LocalLeadStore()
        window = MainWindow(LeadService(store))
    except DatabaseError as error:
        logging.getLogger("leadfinder").exception("Could not open the LeadFinder database.")
        if smoke:
            if smoke_dir is not None:
                smoke_dir.cleanup()
            return 1
        recovered = _recover_from_startup_error(error, MainWindow, LeadService)
        window = recovered if isinstance(recovered, MainWindow) else None

    if window is None:
        if smoke_dir is not None:
            smoke_dir.cleanup()
        return 1

    if smoke:
        window.close()
        try:
            window.service.store.close()
        except Exception:
            pass
        if smoke_dir is not None:
            smoke_dir.cleanup()
        return 0

    window.show()
    should_onboard = show_onboarding
    if should_onboard is None:
        from leadfinder.gui.onboarding import onboarding_completed

        should_onboard = not onboarding_completed(window.settings)
    if should_onboard:
        window.show_welcome()
    return app.exec()


def _recover_from_startup_error(
    error: DatabaseError,
    main_window_cls: type,
    service_cls: type,
) -> object | None:
    from PySide6.QtWidgets import QFileDialog

    from leadfinder.gui.startup_errors import (
        CHOICE_DEMO,
        CHOICE_RESTORE,
        show_startup_failure,
    )
    from leadfinder.paths import data_dir
    from leadfinder.storage.connection import validate_leadfinder_db
    from leadfinder.storage.local_leads import LocalLeadStore

    choice = show_startup_failure(None, str(error))
    if choice == CHOICE_DEMO:
        from leadfinder.demo import ensure_demo_database

        try:
            demo = ensure_demo_database()
            return main_window_cls(service_cls(LocalLeadStore(demo)))
        except DatabaseError as demo_error:
            show_startup_failure(None, str(demo_error))
            return None
    if choice == CHOICE_RESTORE:
        path, _ = QFileDialog.getOpenFileName(
            None, "Restore backup", str(Path.home()), "LeadFinder database (*.db)"
        )
        if not path:
            return None
        try:
            validate_leadfinder_db(Path(path))
            target = data_dir() / "leadfinder.db"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            return main_window_cls(service_cls(LocalLeadStore(target)))
        except (OSError, RestoreError) as restore_error:
            show_startup_failure(None, str(restore_error))
            return None
    return None
