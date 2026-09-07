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


def test_migrates_v4_search_runs(tmp_path: Path) -> None:
    path = tmp_path / "v4.db"
    conn = sqlite3.connect(path)
    conn.executescript(_V1_LEADS)
    migrate(conn)
    conn.execute("UPDATE schema_meta SET version = 4 WHERE id = 1")
    conn.execute(
        """
        INSERT INTO search_runs (
            created_at, business_preset, location, region, country,
            lead_count, high_opportunity_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-01T00:00:00+00:00", "cafe", "Example City", "", "AR", 3, 1),
    )
    conn.commit()
    conn.close()
    store = LocalLeadStore(path)
    assert store.schema_version == CURRENT_SCHEMA_VERSION
    runs = store.list_searches()
    assert runs[0].business_preset == "cafe"
    assert runs[0].campaign_id == 0
    store.close()


def test_migrates_v2_and_v3(tmp_path: Path) -> None:
    path = tmp_path / "v2.db"
    conn = sqlite3.connect(path)
    conn.executescript(_V1_LEADS)
    conn.execute(
        "ALTER TABLE leads_local ADD COLUMN next_follow_up_at TEXT NOT NULL DEFAULT ''"
    )
    conn.execute("ALTER TABLE leads_local ADD COLUMN last_activity_at TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE leads_local ADD COLUMN label TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE leads_local ADD COLUMN opportunity_level TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE leads_local ADD COLUMN opportunity_score INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE leads_local ADD COLUMN has_phone INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """
        CREATE TABLE schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL
        )
        """
    )
    conn.execute("INSERT INTO schema_meta (id, version) VALUES (1, 2)")
    conn.execute(
        """
        INSERT INTO leads_local (
            place_id, contact_status, notes, first_seen_at, last_seen_at,
            last_contacted_at, tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ChIJ_SYNTHETIC_V2",
            "contacted",
            "ok",
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
            "",
            "",
        ),
    )
    conn.commit()
    conn.close()
    store = LocalLeadStore(path)
    assert store.schema_version == CURRENT_SCHEMA_VERSION
    state = store.get("ChIJ_SYNTHETIC_V2")
    assert state is not None
    assert state.contact_status == "contacted"
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


def test_migrates_v5_to_experiments(tmp_path: Path) -> None:
    path = tmp_path / "v5.db"
    conn = sqlite3.connect(path)
    conn.executescript(_V1_LEADS)
    migrate(conn)
    conn.execute("UPDATE schema_meta SET version = 5 WHERE id = 1")
    conn.commit()
    conn.close()
    store = LocalLeadStore(path)
    assert store.schema_version == CURRENT_SCHEMA_VERSION
    experiment = store.create_experiment(name="v5 upgrade", hypothesis="check")
    assert experiment.id >= 1
    store.close()
