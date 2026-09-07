"""Support diagnostics. No secrets, notes, or lead records."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from leadfinder import __version__
from leadfinder.desktop.credentials import groq_key_configured, places_key_configured
from leadfinder.desktop.identity import APP_DISPLAY_NAME
from leadfinder.desktop.runtime import is_frozen
from leadfinder.paths import default_db_path, default_log_path, display_user_path
from leadfinder.storage.schema import CURRENT_SCHEMA_VERSION


def _gui_available() -> bool:
    try:
        import PySide6  # noqa: F401

        return True
    except ImportError:
        return False


def _schema_label(db_path: Path) -> str:
    if not db_path.exists():
        return f"no database yet (current code v{CURRENT_SCHEMA_VERSION})"
    try:
        from leadfinder.storage.connection import validate_leadfinder_db

        version = validate_leadfinder_db(db_path)
        return f"v{version} (code v{CURRENT_SCHEMA_VERSION})"
    except Exception:
        return "unreadable"


def collect_diagnostics(*, db_path: Path | None = None) -> str:
    database = db_path or default_db_path()
    runtime = "packaged" if is_frozen() else "source"
    python = platform.python_version()
    if is_frozen():
        python = f"{python} (bundled)"
    lines = [
        f"{APP_DISPLAY_NAME} version: {__version__}",
        f"Runtime: {runtime}",
        f"Python: {python}",
        f"OS: {platform.system()} {platform.release()} ({platform.machine()})",
        f"Frozen: {'yes' if is_frozen() else 'no'}",
        f"GUI available: {'yes' if _gui_available() else 'no'}",
        f"Schema: {_schema_label(database)}",
        f"Google Places configured: {'yes' if places_key_configured() else 'no'}",
        f"Groq configured: {'yes' if groq_key_configured() else 'no'}",
        f"Database path: {display_user_path(database)}",
        f"Log path: {display_user_path(default_log_path())}",
        "API keys: not included",
        "Lead data: not included",
    ]
    qt = os.environ.get("QT_QPA_PLATFORM", "").strip()
    if qt:
        lines.append(f"QT_QPA_PLATFORM: {qt}")
    exe = Path(sys.executable)
    if is_frozen():
        lines.append(f"Executable: {exe.name}")
    return "\n".join(lines) + "\n"
