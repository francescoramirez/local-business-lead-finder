from __future__ import annotations

from datetime import datetime
from pathlib import Path

from platformdirs import user_data_dir, user_log_dir

from leadfinder.desktop import runtime

APP_NAME = "LeadFinder"
APP_AUTHOR = "LeadFinder"


def os_app_data_dir() -> Path:
    """Default OS app-data folder, ignoring LEADFINDER_DATA_DIR."""
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def data_dir() -> Path:
    override = runtime.env_data_dir_override()
    path = override if override is not None else os_app_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    override = runtime.env_data_dir_override()
    if override is not None:
        path = override / "Logs"
    else:
        path = Path(user_log_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    override = runtime.env_db_override()
    if override is not None:
        return override
    return data_dir() / "leadfinder.db"


def demo_db_path() -> Path:
    return data_dir() / "leadfinder-demo.db"


def default_log_path() -> Path:
    return log_dir() / "leadfinder.log"


def exports_dir() -> Path:
    path = data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_filename(stamp: datetime | None = None, *, demo: bool = False) -> str:
    current = stamp or datetime.now()
    prefix = "leadfinder-demo-backup" if demo else "leadfinder-backup"
    return current.strftime(f"{prefix}-%Y%m%d-%H%M%S.db")


def is_demo_database(path: Path) -> bool:
    try:
        return path.expanduser().resolve() == demo_db_path().expanduser().resolve()
    except OSError:
        return False


def is_user_database(path: Path) -> bool:
    try:
        return path.expanduser().resolve() == (data_dir() / "leadfinder.db").expanduser().resolve()
    except OSError:
        return False


def display_user_path(path: Path) -> str:
    """Show a path without expanding the username when possible."""
    raw = str(path)
    home = str(Path.home())
    if not home:
        return raw
    if raw.startswith(home):
        suffix = raw[len(home) :].lstrip("\\/")
        if os_name_is_windows():
            return r"%USERPROFILE%\\" + suffix.replace("/", "\\") if suffix else r"%USERPROFILE%"
        return "$HOME/" + suffix.replace("\\", "/") if suffix else "$HOME"
    return raw


def os_name_is_windows() -> bool:
    import os

    return os.name == "nt"


def path_is_under_install_dir(path: Path) -> bool:
    root = runtime.install_dir()
    if root is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def user_data_is_writable() -> tuple[bool, str]:
    try:
        directory = data_dir()
        probe = directory / ".leadfinder-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, str(directory)
    except OSError as error:
        return False, str(error)


def runtime_must_not_write_install_dir() -> bool:
    """True when user data lives outside the packaged install directory."""
    if not runtime.is_frozen():
        return True
    return not path_is_under_install_dir(data_dir())
