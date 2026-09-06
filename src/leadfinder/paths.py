from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir, user_log_dir

APP_NAME = "LeadFinder"
APP_AUTHOR = "LeadFinder"


def data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = Path(user_log_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    return data_dir() / "leadfinder.db"


def default_log_path() -> Path:
    return log_dir() / "leadfinder.log"
