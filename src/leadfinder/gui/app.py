from __future__ import annotations

import os
import sys

from leadfinder.errors import DatabaseError, GuiDependencyError


def run_gui() -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
    except ImportError as error:
        raise GuiDependencyError(
            "GUI dependencies are not installed.\n\n"
            'Install them with:\n\n    pip install -e ".[gui]"'
        ) from error

    from leadfinder.gui.main_window import MainWindow
    from leadfinder.gui.styles import LIGHT_QSS
    from leadfinder.logging_setup import configure_logging

    configure_logging()
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv)
    app.setApplicationName("LeadFinder")
    app.setOrganizationName("LeadFinder")
    app.setStyle("Fusion")
    app.setStyleSheet(LIGHT_QSS)
    try:
        window = MainWindow()
    except DatabaseError as error:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(None, "LeadFinder", str(error))
        return 1
    window.show()
    return app.exec()
