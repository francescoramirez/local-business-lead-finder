from __future__ import annotations

from pathlib import Path

from leadfinder.desktop.diagnostics import collect_diagnostics


def test_diagnostics_has_required_fields_without_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LEADFINDER_TEST_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LEADFINDER_TEST_GROQ_API_KEY", raising=False)
    text = collect_diagnostics(db_path=tmp_path / "missing.db")
    assert "LeadFinder version:" in text
    assert "Runtime:" in text
    assert "Python:" in text
    assert "OS:" in text
    assert "Schema:" in text
    assert "Google Places configured: no" in text
    assert "Groq configured: no" in text
    assert "API keys: not included" in text
    assert "Lead data: not included" in text
    assert "Frozen: no" in text
    assert "AIza" not in text
    assert "gsk_" not in text
