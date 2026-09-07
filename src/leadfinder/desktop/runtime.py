"""Frozen vs development resource resolution. One place for sys._MEIPASS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SMOKE_EXIT_ENV = "LEADFINDER_SMOKE_EXIT"
DB_PATH_ENV = "LEADFINDER_DB_PATH"
DATA_DIR_ENV = "LEADFINDER_DATA_DIR"
PACKAGED_TEST_ENV = "LEADFINDER_PACKAGED_TEST"
PACKAGED_REPORT_ENV = "LEADFINDER_PACKAGED_REPORT"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def package_root() -> Path:
    """leadfinder package directory (contains desktop/, gui/, …)."""
    return Path(__file__).resolve().parent.parent


def application_root() -> Path:
    """Bundle root when frozen; package root in development."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return package_root()


def install_dir() -> Path | None:
    """Directory that contains the packaged executable, if any."""
    if not is_frozen():
        return None
    return Path(sys.executable).resolve().parent


def resource_path(*parts: str) -> Path:
    """Resolve a file shipped with the application (icons, licenses, …)."""
    return application_root().joinpath(*parts)


def smoke_exit_requested() -> bool:
    return os.environ.get(SMOKE_EXIT_ENV, "").strip() == "1"


def env_db_override() -> Path | None:
    raw = os.environ.get(DB_PATH_ENV, "").strip()
    if not raw:
        return None
    return Path(raw)


def env_data_dir_override() -> Path | None:
    raw = os.environ.get(DATA_DIR_ENV, "").strip()
    if not raw:
        return None
    return Path(raw)


def packaged_test_requested() -> str:
    return os.environ.get(PACKAGED_TEST_ENV, "").strip()


def packaged_report_path() -> Path | None:
    raw = os.environ.get(PACKAGED_REPORT_ENV, "").strip()
    if not raw:
        return None
    return Path(raw)
