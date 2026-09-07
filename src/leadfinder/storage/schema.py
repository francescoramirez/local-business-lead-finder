"""Incremental sqlite3 schema for local workflow data."""

from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 7

_V1_LEADS = """
CREATE TABLE IF NOT EXISTS leads_local (
    place_id TEXT PRIMARY KEY,
    contact_status TEXT NOT NULL DEFAULT 'new',
    notes TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_contacted_at TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT ''
);
"""


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: sqlite3.Connection, table: str, definition: str) -> None:
    name = definition.split()[0]
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def schema_version(conn: sqlite3.Connection) -> int:
    if _table_exists(conn, "schema_meta"):
        row = conn.execute("SELECT version FROM schema_meta WHERE id = 1").fetchone()
        if row is not None:
            return int(row[0])
    if _table_exists(conn, "leads_local"):
        return 1
    return 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_meta ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL)"
    )
    conn.execute(
        "INSERT INTO schema_meta (id, version) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET version=excluded.version",
        (version,),
    )


def migrate(conn: sqlite3.Connection) -> int:
    """Apply incremental migrations. Safe to run repeatedly."""
    conn.execute("PRAGMA foreign_keys=ON")
    version = schema_version(conn)
    if version < 1:
        conn.executescript(_V1_LEADS)
        version = 1
        _set_version(conn, version)
    if version < 2:
        _add_column(conn, "leads_local", "next_follow_up_at TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "last_activity_at TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "label TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "opportunity_level TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "opportunity_score INTEGER NOT NULL DEFAULT 0")
        _add_column(conn, "leads_local", "has_phone INTEGER NOT NULL DEFAULT 0")
        version = 2
        _set_version(conn, version)
    if version < 3:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                contact_method TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(place_id) REFERENCES leads_local(place_id)
            );
            CREATE INDEX IF NOT EXISTS idx_activities_place_created
                ON activities(place_id, created_at);
            """
        )
        version = 3
        _set_version(conn, version)
    if version < 4:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS search_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                business_preset TEXT NOT NULL,
                location TEXT NOT NULL,
                region TEXT NOT NULL,
                country TEXT NOT NULL,
                lead_count INTEGER NOT NULL,
                high_opportunity_count INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_search_runs_created ON search_runs(created_at);
            CREATE INDEX IF NOT EXISTS idx_leads_status ON leads_local(contact_status);
            CREATE INDEX IF NOT EXISTS idx_leads_follow_up ON leads_local(next_follow_up_at);
            """
        )
        version = 4
        _set_version(conn, version)
    if version < 5:
        _add_column(conn, "search_runs", "campaign_id INTEGER")
        _add_column(conn, "leads_local", "business_preset TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "source_location TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "region TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "country TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "website_status TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "leads_local", "campaign_id INTEGER")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                business_preset TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT '',
                auto_created INTEGER NOT NULL DEFAULT 0,
                local_day TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS campaign_leads (
                campaign_id INTEGER NOT NULL,
                place_id TEXT NOT NULL,
                PRIMARY KEY (campaign_id, place_id),
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(place_id) REFERENCES leads_local(place_id)
            );
            CREATE INDEX IF NOT EXISTS idx_campaigns_created ON campaigns(created_at);
            CREATE INDEX IF NOT EXISTS idx_campaign_leads_place ON campaign_leads(place_id);
            CREATE INDEX IF NOT EXISTS idx_activities_created ON activities(created_at);
            CREATE INDEX IF NOT EXISTS idx_search_runs_campaign ON search_runs(campaign_id);
            """
        )
        version = 5
        _set_version(conn, version)
    if version < 6:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                hypothesis TEXT NOT NULL DEFAULT '',
                business_preset TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                digital_presence TEXT NOT NULL DEFAULT '',
                opportunity_level TEXT NOT NULL DEFAULT '',
                target_metric TEXT NOT NULL DEFAULT 'contact_to_interest',
                notes TEXT NOT NULL DEFAULT '',
                observations TEXT NOT NULL DEFAULT '',
                conclusion TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS experiment_campaigns (
                experiment_id INTEGER NOT NULL,
                campaign_id INTEGER NOT NULL,
                PRIMARY KEY (experiment_id, campaign_id),
                FOREIGN KEY(experiment_id) REFERENCES experiments(id),
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
            );
            CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
            CREATE INDEX IF NOT EXISTS idx_experiment_campaigns_campaign
                ON experiment_campaigns(campaign_id);
            """
        )
        version = 6
        _set_version(conn, version)
    if version < 7:
        _add_column(conn, "leads_local", "manual_priority TEXT NOT NULL DEFAULT 'normal'")
        version = 7
        _set_version(conn, version)
    conn.commit()
    return version
