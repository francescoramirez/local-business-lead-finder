from __future__ import annotations

import sqlite3
from pathlib import Path

from leadfinder.storage.local_leads import LocalLeadStore
from leadfinder.storage.schema import _V1_LEADS, CURRENT_SCHEMA_VERSION, migrate, schema_version


def test_new_database_is_current_version(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "new.db")
    assert store.schema_version == CURRENT_SCHEMA_VERSION
    store.close()


def test_migrates_v1_and_preserves_rows(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(_V1_LEADS)
    conn.execute(
        """
        INSERT INTO leads_local (
            place_id, contact_status, notes, first_seen_at, last_seen_at,
            last_contacted_at, tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ChIJ_SYNTHETIC_501",
            "interested",
            "Keep this note",
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
            "2026-01-01T12:00:00+00:00",
            "priority",
        ),
    )
    conn.commit()
    conn.close()

    store = LocalLeadStore(path)
    assert store.schema_version == CURRENT_SCHEMA_VERSION
    state = store.get("ChIJ_SYNTHETIC_501")
    assert state is not None
    assert state.contact_status == "interested"
    assert state.notes == "Keep this note"
    assert state.tags == "priority"
    assert state.first_seen_at.startswith("2026-01-01")
    assert state.next_follow_up_at == ""
    store.close()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "id.db"
    conn = sqlite3.connect(path)
    first = migrate(conn)
    second = migrate(conn)
    assert first == CURRENT_SCHEMA_VERSION
    assert second == CURRENT_SCHEMA_VERSION
    assert schema_version(conn) == CURRENT_SCHEMA_VERSION
    conn.close()
