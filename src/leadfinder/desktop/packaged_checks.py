"""Frozen-app QA hooks. Writes a JSON report. Never prints secret values."""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from leadfinder.desktop.runtime import (
    is_frozen,
    packaged_report_path,
    packaged_test_requested,
)
from leadfinder.paths import os_app_data_dir
from leadfinder.storage.schema import CURRENT_SCHEMA_VERSION

DUMMY_PLACES = "packaged-qa-dummy-places-not-a-real-key"
ZONE_NAMES = (
    "America/Argentina/Buenos_Aires",
    "America/New_York",
    "UTC",
)


def run_if_requested() -> int | None:
    requested = packaged_test_requested()
    if not requested:
        return None
    names = _expand(requested)
    results: dict[str, Any] = {
        "frozen": is_frozen(),
        "checks": {},
        "ok": True,
    }
    for name in names:
        try:
            results["checks"][name] = _DISPATCH[name]()
        except Exception as error:
            results["ok"] = False
            results["checks"][name] = {
                "ok": False,
                "error": str(error),
                "traceback": traceback.format_exc(),
            }
        else:
            payload = results["checks"][name]
            if isinstance(payload, dict) and not payload.get("ok", True):
                results["ok"] = False
    _write_report(results)
    return 0 if results["ok"] else 1


def _expand(requested: str) -> list[str]:
    if requested.strip().lower() in {"1", "all"}:
        return list(_DISPATCH)
    names = [item.strip().lower() for item in requested.split(",") if item.strip()]
    unknown = [name for name in names if name not in _DISPATCH]
    if unknown:
        raise RuntimeError(f"Unknown packaged test(s): {', '.join(unknown)}")
    return names


def _write_report(payload: dict[str, Any]) -> None:
    target = packaged_report_path()
    if target is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ok(**extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": True}
    body.update(extra)
    return body


def _fail(message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": False, "error": message}
    body.update(extra)
    return body


def _check_startup() -> dict[str, Any]:
    return _ok(frozen=is_frozen())


def _check_sqlite() -> dict[str, Any]:
    from leadfinder.storage.local_leads import LocalLeadStore

    root = Path(os.environ.get("LEADFINDER_DATA_DIR", "")).expanduser()
    if not str(root):
        return _fail("LEADFINDER_DATA_DIR is required for packaged sqlite checks")
    db_path = root / "qa-sqlite.db"
    store = LocalLeadStore(db_path)
    version = store.schema_version
    store.mark_seen("ChIJ_PACKAGED_QA_001", label="Packaged SQLite Cafe")
    store.set_notes("ChIJ_PACKAGED_QA_001", "qa-note")
    store.close()
    again = LocalLeadStore(db_path)
    state = again.get("ChIJ_PACKAGED_QA_001")
    again_version = again.schema_version
    again.close()
    if state is None:
        return _fail("lead missing after reopen")
    if state.notes != "qa-note":
        return _fail("notes did not persist")
    if version != CURRENT_SCHEMA_VERSION or again_version != CURRENT_SCHEMA_VERSION:
        return _fail(f"schema {version}/{again_version}, expected {CURRENT_SCHEMA_VERSION}")
    return _ok(schema=again_version)


def _check_demo() -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    owner_db = os_app_data_dir() / "leadfinder.db"
    before = (owner_db.exists(), owner_db.stat().st_mtime_ns if owner_db.exists() else 0)
    from leadfinder.demo import ensure_demo_database
    from leadfinder.paths import is_user_database

    demo = ensure_demo_database()
    if is_user_database(demo):
        return _fail("demo path resolved to the user database")
    from PySide6.QtWidgets import QApplication

    from leadfinder.application.service import LeadService
    from leadfinder.desktop.identity import apply_qt_identity
    from leadfinder.gui.main_window import MainWindow
    from leadfinder.storage.local_leads import LocalLeadStore

    app = QApplication.instance() or QApplication(["leadfinder-packaged-qa"])
    apply_qt_identity(app)
    store = LocalLeadStore(demo)
    window = MainWindow(LeadService(store))
    window.close()
    store.close()
    after = (owner_db.exists(), owner_db.stat().st_mtime_ns if owner_db.exists() else 0)
    if before != after:
        return _fail("owner leadfinder.db changed during demo packaged test")
    return _ok(demo_exists=demo.exists(), demo_name=demo.name)


def _check_keyring() -> dict[str, Any]:
    from leadfinder.desktop.credentials import (
        delete_secret,
        places_key_configured,
        save_secret,
    )

    if os.environ.get("LEADFINDER_KEYRING_ACCOUNT_PLACES", "").strip() == "":
        return _fail(
            "LEADFINDER_KEYRING_ACCOUNT_PLACES is required so owner credentials stay untouched"
        )
    save_secret("places", DUMMY_PLACES)
    configured_after_save = places_key_configured()
    delete_secret("places")
    configured_after_delete = places_key_configured()
    if not configured_after_save:
        return _fail("configured was false after save")
    if configured_after_delete:
        return _fail("configured was true after delete")
    return _ok(save_configured=True, delete_configured=False)


def _check_env_precedence() -> dict[str, Any]:
    from leadfinder.desktop.credentials import SOURCE_ENVIRONMENT, lookup_places_key

    found = lookup_places_key()
    if found.source != SOURCE_ENVIRONMENT:
        return _fail(f"expected environment source, got {found.source}")
    if not found.value:
        return _fail("environment key was empty")
    return _ok(source=found.source, value_length=len(found.value))


def _check_backup() -> dict[str, Any]:
    from leadfinder.storage.connection import validate_leadfinder_db
    from leadfinder.storage.local_leads import LocalLeadStore

    root = Path(os.environ.get("LEADFINDER_DATA_DIR", "")).expanduser()
    if not str(root):
        return _fail("LEADFINDER_DATA_DIR is required for packaged backup checks")
    db_path = root / "qa-backup-src.db"
    dest = root / "qa-backup-copy.db"
    store = LocalLeadStore(db_path)
    store.mark_seen("ChIJ_PACKAGED_BACKUP", label="Backup Cafe")
    store.backup(dest)
    store.close()
    version = validate_leadfinder_db(dest)
    again = LocalLeadStore(dest)
    state = again.get("ChIJ_PACKAGED_BACKUP")
    again.close()
    if state is None or state.label != "Backup Cafe":
        return _fail("backup did not contain the written lead")
    return _ok(schema=version, sqlite_backup_api=True)


def _check_workspace() -> dict[str, Any]:
    from leadfinder.application.service import LeadService
    from leadfinder.storage.local_leads import LocalLeadStore

    root = Path(os.environ.get("LEADFINDER_DATA_DIR", "")).expanduser()
    if not str(root):
        return _fail("LEADFINDER_DATA_DIR is required for packaged workspace checks")
    db_path = root / "qa-workspace.db"
    zip_path = root / "qa-workspace.zip"
    store = LocalLeadStore(db_path)
    store.mark_seen("ChIJ_PACKAGED_WS", label="Workspace Cafe")
    store.set_notes("ChIJ_PACKAGED_WS", "ws-note")
    service = LeadService(store)
    service.export_workspace(zip_path)
    store.close()
    other = LocalLeadStore(root / "qa-workspace-import.db")
    LeadService(other).import_workspace(zip_path)
    state = other.get("ChIJ_PACKAGED_WS")
    other.close()
    if state is None or state.notes != "ws-note":
        return _fail("workspace import did not restore lead notes")
    return _ok(zip_exists=zip_path.exists())


def _check_zoneinfo() -> dict[str, Any]:
    from leadfinder.analytics import coerce_timezone

    resolved: dict[str, str] = {}
    for name in ZONE_NAMES:
        tz = coerce_timezone(name)
        if not isinstance(tz, ZoneInfo):
            return _fail(f"{name} did not resolve to ZoneInfo", resolved=type(tz).__name__)
        key = str(getattr(tz, "key", name))
        if name != "UTC" and key != name:
            return _fail(f"{name} resolved to {key}")
        datetime.now(tz)
        resolved[name] = key
    return _ok(zones=resolved)


def _check_diagnostics() -> dict[str, Any]:
    from leadfinder.desktop.diagnostics import collect_diagnostics

    text = collect_diagnostics()
    lowered = text.lower()
    if "frozen: yes" not in lowered and not is_frozen():
        return _fail("source diagnostics should say Frozen: no; this check is for packaged builds")
    if is_frozen() and "frozen: yes" not in lowered:
        return _fail("packaged diagnostics missing Frozen: yes")
    if DUMMY_PLACES.lower() in lowered:
        return _fail("diagnostics contained dummy key")
    if "AIza" in text or "gsk_" in text:
        return _fail("diagnostics contained key-like prefixes")
    return _ok(frozen_line="Frozen: yes" in text, length=len(text))


def _check_settings_imports() -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from leadfinder.desktop import credentials, diagnostics
    from leadfinder.gui import about_dialog, onboarding, settings_dialog
    from leadfinder.gui.app import run_gui

    QApplication.instance() or QApplication(["leadfinder-packaged-qa"])
    names = [
        settings_dialog.SettingsDialog.__name__,
        about_dialog.AboutDialog.__name__,
        onboarding.__name__,
        credentials.__name__,
        diagnostics.__name__,
        run_gui.__name__,
    ]
    return _ok(imported=names)


_DISPATCH = {
    "startup": _check_startup,
    "sqlite": _check_sqlite,
    "demo": _check_demo,
    "keyring": _check_keyring,
    "env_precedence": _check_env_precedence,
    "backup": _check_backup,
    "workspace": _check_workspace,
    "zoneinfo": _check_zoneinfo,
    "diagnostics": _check_diagnostics,
    "settings": _check_settings_imports,
}
