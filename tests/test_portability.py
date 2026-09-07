from __future__ import annotations

from pathlib import Path

import pytest

from leadfinder.application.service import LeadService
from leadfinder.doctor import format_doctor, run_doctor
from leadfinder.errors import RestoreError, WorkspaceError
from leadfinder.paths import backup_filename
from leadfinder.storage.local_leads import LocalLeadStore, validate_leadfinder_db
from leadfinder.workspace import WORKSPACE_FORMAT_VERSION, export_workspace, import_workspace


def test_backup_restore_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "live.db"
    store = LocalLeadStore(db)
    store.mark_seen("ChIJ_SYNTH_R1", label="Cafe Example", business_preset="cafe")
    backup = tmp_path / backup_filename()
    store.backup(backup)
    store.mark_seen("ChIJ_SYNTH_R2", label="Later Cafe")
    assert store.get("ChIJ_SYNTH_R2") is not None
    safety = store.restore(backup)
    assert safety.exists()
    assert store.get("ChIJ_SYNTH_R1") is not None
    assert store.get("ChIJ_SYNTH_R2") is None
    store.close()


def test_invalid_backup_rejected(tmp_path: Path) -> None:
    junk = tmp_path / "not.db"
    junk.write_bytes(b"this is not sqlite")
    with pytest.raises(RestoreError):
        validate_leadfinder_db(junk)
    live = LocalLeadStore(tmp_path / "live.db")
    with pytest.raises(RestoreError):
        live.restore(junk)
    live.close()


def test_workspace_export_import_merge(tmp_path: Path) -> None:
    source = LocalLeadStore(tmp_path / "src.db")
    source.mark_seen(
        "ChIJ_SYNTH_W1",
        label="Export Cafe",
        business_preset="cafe",
        source_location="Example City",
        website_status="no_website",
    )
    source.set_contact_status("ChIJ_SYNTH_W1", "contacted")
    campaign = source.create_campaign(name="Export Campaign", location="Example City")
    source.attach_leads(campaign.id, ["ChIJ_SYNTH_W1"])
    source.create_experiment(name="Export Experiment", hypothesis="Try no website")
    zip_path = tmp_path / "workspace.zip"
    export_workspace(source, zip_path, settings={"location": "Example City"})
    source.close()

    dest = LocalLeadStore(tmp_path / "dst.db")
    dest.mark_seen("ChIJ_SYNTH_KEEP", label="Keep me")
    added = import_workspace(dest, zip_path)
    assert added["leads"] == 1
    assert dest.get("ChIJ_SYNTH_W1") is not None
    assert dest.get("ChIJ_SYNTH_KEEP") is not None
    again = import_workspace(dest, zip_path)
    assert again["skipped_leads"] >= 1
    dest.close()


def test_invalid_workspace_rejected(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "w.db")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(WorkspaceError):
        import_workspace(store, bad)
    store.close()


def test_doctor_on_healthy_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    store = LocalLeadStore(tmp_path / "doc.db")
    report = run_doctor(store.path)
    text = format_doctor(report)
    assert "LeadFinder Doctor" in text
    assert "Database" in text
    assert f"v{store.schema_version}" in text
    assert "Pricing catalog" in text
    assert "gsk_" not in text.lower()
    assert "aiza" not in text.lower()
    assert report.ok()
    store.close()
    assert WORKSPACE_FORMAT_VERSION == 1


def test_service_backup_and_doctor(tmp_path: Path) -> None:
    service = LeadService(LocalLeadStore(tmp_path / "svc.db"))
    path = service.backup(tmp_path / "copy.db")
    assert path.exists()
    report = service.doctor()
    assert report.data_path.endswith("svc.db")
