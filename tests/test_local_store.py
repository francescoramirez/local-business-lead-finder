from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from leadfinder.models import utc_now_iso
from leadfinder.storage.local_leads import LocalLeadStore
from leadfinder.workflow import ActivityType, is_overdue


def test_status_and_notes_persist_across_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "leads.db"
    store = LocalLeadStore(path)
    store.mark_seen("ChIJ_SYNTHETIC_201")
    store.set_contact_status("ChIJ_SYNTHETIC_201", "contacted")
    store.set_notes("ChIJ_SYNTHETIC_201", "Called on Monday")
    store.close()

    reopened = LocalLeadStore(path)
    state = reopened.get("ChIJ_SYNTHETIC_201")
    assert state is not None
    assert state.contact_status == "contacted"
    assert state.notes == "Called on Monday"
    assert state.first_seen_at
    assert state.last_contacted_at
    reopened.close()


def test_follow_up_activity_and_first_seen(tmp_path: Path) -> None:
    now = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)
    store = LocalLeadStore(tmp_path / "wf.db")
    first = store.mark_seen("ChIJ_SYNTHETIC_502", seen_at=now.isoformat())
    later = now + timedelta(days=1)
    store.mark_seen("ChIJ_SYNTHETIC_502", seen_at=later.isoformat(), label="Harbor Cafe")
    store.set_follow_up(
        "ChIJ_SYNTHETIC_502",
        (now - timedelta(hours=3)).isoformat(),
        now=later,
    )
    store.set_tags("ChIJ_SYNTHETIC_502", "priority, call")
    store.set_contact_status("ChIJ_SYNTHETIC_502", "contacted", now=later)
    activities = store.list_activities("ChIJ_SYNTHETIC_502")
    types = [item.activity_type for item in activities]
    assert ActivityType.DISCOVERED.value in types
    assert ActivityType.FOLLOW_UP.value in types
    assert ActivityType.STATUS_CHANGE.value in types
    assert activities[0].created_at >= activities[-1].created_at
    state = store.get("ChIJ_SYNTHETIC_502")
    assert state is not None
    assert state.first_seen_at == first.first_seen_at
    assert state.last_seen_at == later.isoformat()
    assert state.label == "Harbor Cafe"
    assert "priority" in state.tags
    assert is_overdue(state.contact_status, state.next_follow_up_at, now=now)
    store.close()


def test_transaction_rollback_keeps_notes(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "tx.db")
    store.mark_seen("ChIJ_SYNTHETIC_503")
    try:
        with store.transaction():
            store.set_notes("ChIJ_SYNTHETIC_503", "should not stick", commit=False)
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    state = store.get("ChIJ_SYNTHETIC_503")
    assert state is not None
    assert state.notes == ""
    store.close()


def test_backup_copies_rows(tmp_path: Path) -> None:
    source = tmp_path / "src.db"
    dest = tmp_path / "copy.db"
    store = LocalLeadStore(source)
    store.set_notes("ChIJ_SYNTHETIC_504", "backed up")
    store.backup(dest)
    store.close()
    restored = LocalLeadStore(dest)
    state = restored.get("ChIJ_SYNTHETIC_504")
    assert state is not None
    assert state.notes == "backed up"
    restored.close()


def test_mark_seen_keeps_existing_status(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    store.set_contact_status("ChIJ_SYNTHETIC_202", "interested")
    later = utc_now_iso()
    state = store.mark_seen("ChIJ_SYNTHETIC_202", seen_at=later)
    assert state.contact_status == "interested"
    assert state.last_seen_at == later
    store.close()
