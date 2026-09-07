"""SQLite connection, pragmas, backup, and restore."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from leadfinder.errors import BackupError, DatabaseError, RestoreError
from leadfinder.paths import default_db_path
from leadfinder.storage.schema import _table_exists, migrate, schema_version

LOGGER = logging.getLogger("leadfinder")
BUSY_TIMEOUT_MS = 5000


def apply_connection_pragmas(conn: sqlite3.Connection) -> None:
    """WAL is kept: backup uses sqlite3 backup API, which copies the live WAL-backed DB."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")


def open_database(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    apply_connection_pragmas(conn)
    migrate(conn)
    return conn


def validate_leadfinder_db(path: Path) -> int:
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise RestoreError("Backup file is not a valid SQLite database.") from error
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row is None or str(row[0]).lower() != "ok":
            raise RestoreError("Backup failed SQLite integrity check.")
        if not _table_exists(conn, "leads_local") and not _table_exists(conn, "schema_meta"):
            raise RestoreError("File is not a LeadFinder database.")
        return schema_version(conn)
    except sqlite3.Error as error:
        raise RestoreError("Backup file is not a valid SQLite database.") from error
    finally:
        conn.close()


class ConnectionMixin:
    path: Path
    _conn: sqlite3.Connection

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = open_database(self.path)
        except sqlite3.DatabaseError as error:
            raise DatabaseError(
                "The local LeadFinder database could not be opened. "
                "It may be damaged. Restore a backup with File > Restore data, "
                "or run: leadfinder doctor"
            ) from error

    @property
    def schema_version(self) -> int:
        return schema_version(self._conn)

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            self._conn.execute("BEGIN")
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def backup(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            target = sqlite3.connect(destination)
            try:
                self._conn.backup(target)
            finally:
                target.close()
        except sqlite3.Error as error:
            raise BackupError(f"Could not backup the local database: {error}") from error
        return destination

    def restore(self, source: Path) -> Path:
        source = Path(source)
        if not source.exists():
            raise RestoreError("Backup file not found.")
        validate_leadfinder_db(source)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safety = self.path.with_name(f"leadfinder-pre-restore-{stamp}.db")
        self.backup(safety)
        self._conn.close()
        try:
            for extra in (Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
                if extra.exists():
                    extra.unlink()
            shutil.copy2(source, self.path)
            self._open()
        except (OSError, sqlite3.Error, DatabaseError) as error:
            try:
                shutil.copy2(safety, self.path)
                self._open()
            except Exception:
                LOGGER.exception("Could not reopen the safety database after a failed restore.")
            raise RestoreError(
                "Could not restore the backup. A safety copy of the previous database "
                f"was saved to {safety}."
            ) from error
        return safety

    def _open(self) -> None:
        self._conn = open_database(self.path)
