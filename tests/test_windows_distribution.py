from __future__ import annotations

from pathlib import Path


def test_installer_script_is_per_user_and_keeps_app_data() -> None:
    text = Path("packaging/installer/LeadFinder.iss").read_text(encoding="utf-8")
    assert "AppId={{7C3E9B1A-4F2D-4A8E-9C11-A1B2C3D4E5F6}" in text
    assert "AppPublisher=FrancescoRamirezC" in text or "MyAppPublisher" in text
    assert "PrivilegesRequired=lowest" in text
    assert r"DefaultDirName={localappdata}\Programs\LeadFinder" in text
    assert "UninstallDisplayIcon={app}" in text
    assert "ArchitecturesAllowed=x64compatible" in text
    assert "WorkingDir: \"{app}\"" in text
    assert "[UninstallDelete]" not in text
    assert "leadfinder.db" not in text.lower() or "not deleted" in text.lower()
    assert "UninstallSilent" in text
    assert "LicenseFile=" in text


def test_build_script_finds_inno_and_python312() -> None:
    text = Path("packaging/build_windows.ps1").read_text(encoding="utf-8")
    assert "Resolve-Python312" in text
    assert "Inno Setup 6" in text
    assert "leadfinder-build" in text
    assert "sharing violation" in text
    assert "dist\\release" in text or "dist/release" in text


def test_clean_windows_doc_exists() -> None:
    text = Path("docs/CLEAN_WINDOWS_TEST.md").read_text(encoding="utf-8")
    assert "Try Demo" in text
    assert "SHA256" in text or "SHA-256" in text
    assert "no Python" in text.lower() or "does **not** have" in text
    assert "leadfinder.db" in text
