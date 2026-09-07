from __future__ import annotations

from pathlib import Path

from leadfinder.desktop import packaged_checks
from leadfinder.storage.schema import CURRENT_SCHEMA_VERSION


def test_packaged_sqlite_check_uses_data_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEADFINDER_DATA_DIR", str(tmp_path))
    result = packaged_checks._check_sqlite()
    assert result["ok"] is True
    assert result["schema"] == CURRENT_SCHEMA_VERSION
    assert (tmp_path / "qa-sqlite.db").is_file()


def test_packaged_zoneinfo_check() -> None:
    result = packaged_checks._check_zoneinfo()
    assert result["ok"] is True
    assert "America/Argentina/Buenos_Aires" in result["zones"]
