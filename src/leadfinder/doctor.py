"""Local health checks. Never print secrets."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from leadfinder.config import load_env_file, places_key_configured
from leadfinder.paths import default_db_path
from leadfinder.storage.schema import CURRENT_SCHEMA_VERSION, schema_version


@dataclass
class DoctorCheck:
    name: str
    status: str
    detail: str


@dataclass
class DoctorReport:
    checks: list[DoctorCheck]
    data_path: str

    def ok(self) -> bool:
        return all(item.status != "FAIL" for item in self.checks)


def _gui_available() -> tuple[str, str]:
    try:
        import PySide6  # noqa: F401

        return "OK", "available"
    except ImportError:
        return "WARN", 'missing — install with pip install -e ".[gui]"'


def _groq_configured() -> bool:
    load_env_file()
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def _connect_sqlite(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    return sqlite3.connect(path)


def run_doctor(path: Path | None = None) -> DoctorReport:
    db_path = path or default_db_path()
    checks: list[DoctorCheck] = []
    try:
        conn = _connect_sqlite(db_path, readonly=False)
    except sqlite3.OperationalError:
        try:
            conn = sqlite3.connect(db_path)
        except sqlite3.Error as error:
            checks.append(
                DoctorCheck("Database", "FAIL", f"could not open ({type(error).__name__})")
            )
            gui_status, gui_detail = _gui_available()
            checks.extend(
                [
                    DoctorCheck("Schema", "FAIL", "database unavailable"),
                    DoctorCheck(
                        "Google Places",
                        "OK" if places_key_configured() else "WARN",
                        "configured" if places_key_configured() else "not configured",
                    ),
                    DoctorCheck(
                        "Groq",
                        "OK" if _groq_configured() else "WARN",
                        "configured" if _groq_configured() else "not configured",
                    ),
                    DoctorCheck("GUI", gui_status, gui_detail),
                    DoctorCheck("Local data path", "OK", str(db_path)),
                ]
            )
            return DoctorReport(checks=checks, data_path=str(db_path))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        integrity_ok = integrity is not None and str(integrity[0]).lower() == "ok"
        checks.append(
            DoctorCheck(
                "Database",
                "OK" if integrity_ok else "FAIL",
                "OK" if integrity_ok else "integrity check failed",
            )
        )
        version = schema_version(conn)
        current = version == CURRENT_SCHEMA_VERSION
        checks.append(
            DoctorCheck(
                "Schema",
                "OK" if current else "WARN",
                f"v{version} current"
                if current
                else f"v{version} (expected v{CURRENT_SCHEMA_VERSION})"
            )
        )
        try:
            conn.execute("CREATE TEMP TABLE leadfinder_doctor_probe (x INTEGER)")
            conn.execute("INSERT INTO leadfinder_doctor_probe(x) VALUES (1)")
            row = conn.execute("SELECT x FROM leadfinder_doctor_probe").fetchone()
            conn.execute("DROP TABLE leadfinder_doctor_probe")
            write_ok = row is not None and int(row[0]) == 1
        except sqlite3.Error:
            write_ok = False
        checks.append(
            DoctorCheck(
                "Read/write",
                "OK" if write_ok else "FAIL",
                "temp probe succeeded" if write_ok else "temp probe failed",
            )
        )
    finally:
        conn.close()
    checks.append(
        DoctorCheck(
            "Google Places",
            "OK" if places_key_configured() else "WARN",
            "configured" if places_key_configured() else "not configured",
        )
    )
    checks.append(
        DoctorCheck(
            "Groq",
            "OK" if _groq_configured() else "WARN",
            "configured" if _groq_configured() else "not configured",
        )
    )
    gui_status, gui_detail = _gui_available()
    checks.append(DoctorCheck("GUI", gui_status, gui_detail))
    checks.append(DoctorCheck("Local data path", "OK", str(db_path)))
    return DoctorReport(checks=checks, data_path=str(db_path))


def format_doctor(report: DoctorReport) -> str:
    width = max(len(item.name) for item in report.checks)
    lines = ["LeadFinder Doctor", ""]
    for item in report.checks:
        lines.append(f"{item.name.ljust(width)}  {item.detail}")
    return "\n".join(lines)
