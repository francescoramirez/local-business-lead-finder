from __future__ import annotations

from pathlib import Path

from leadfinder.models import utc_now_iso
from leadfinder.storage.local_leads import LocalLeadStore


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


def test_mark_seen_keeps_existing_status(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "leads.db")
    store.set_contact_status("ChIJ_SYNTHETIC_202", "interested")
    later = utc_now_iso()
    state = store.mark_seen("ChIJ_SYNTHETIC_202", seen_at=later)
    assert state.contact_status == "interested"
    assert state.last_seen_at == later
    store.close()
