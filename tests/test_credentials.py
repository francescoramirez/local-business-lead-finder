from __future__ import annotations

from pathlib import Path

from leadfinder.desktop.credentials import (
    SOURCE_ENVIRONMENT,
    SOURCE_KEYRING,
    SOURCE_NONE,
    SOURCE_TEST,
    MemorySecretBackend,
    delete_secret,
    get_places_api_key,
    lookup_groq_key,
    lookup_places_key,
    save_secret,
    set_secret_backend_for_tests,
)
from leadfinder.desktop.diagnostics import collect_diagnostics
from leadfinder.errors import CredentialStoreError, MissingApiKeyError


def teardown_function() -> None:
    set_secret_backend_for_tests(None)


def test_test_override_beats_env_and_store(monkeypatch) -> None:
    backend = MemorySecretBackend()
    backend.set_password("LeadFinder", "google-places-api", "from-store")
    set_secret_backend_for_tests(backend)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "from-env")
    monkeypatch.setenv("LEADFINDER_TEST_PLACES_API_KEY", "from-test")
    found = lookup_places_key()
    assert found.source == SOURCE_TEST
    assert found.value == "from-test"


def test_environment_beats_keyring(monkeypatch) -> None:
    backend = MemorySecretBackend()
    backend.set_password("LeadFinder", "google-places-api", "from-store")
    set_secret_backend_for_tests(backend)
    monkeypatch.delenv("LEADFINDER_TEST_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "from-env")
    found = lookup_places_key()
    assert found.source == SOURCE_ENVIRONMENT
    assert get_places_api_key() == "from-env"


def test_keyring_used_when_env_empty(monkeypatch) -> None:
    backend = MemorySecretBackend()
    set_secret_backend_for_tests(backend)
    monkeypatch.delenv("LEADFINDER_TEST_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    save_secret("places", "stored-secret")
    found = lookup_places_key()
    assert found.source == SOURCE_KEYRING
    assert found.value == "stored-secret"
    delete_secret("places")
    assert lookup_places_key().source == SOURCE_NONE


def test_missing_key_raises(monkeypatch) -> None:
    set_secret_backend_for_tests(MemorySecretBackend())
    monkeypatch.delenv("LEADFINDER_TEST_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    try:
        get_places_api_key()
    except MissingApiKeyError:
        pass
    else:
        raise AssertionError("expected MissingApiKeyError")


def test_empty_save_rejected() -> None:
    set_secret_backend_for_tests(MemorySecretBackend())
    try:
        save_secret("places", "  ")
    except CredentialStoreError:
        return
    raise AssertionError("expected CredentialStoreError")


def test_diagnostics_and_workspace_exclude_keys(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEADFINDER_TEST_PLACES_API_KEY", "AIzaSyTESTNOTAREALKEY99")
    monkeypatch.setenv("LEADFINDER_TEST_GROQ_API_KEY", "gsk_testnotarealkey99")
    text = collect_diagnostics(db_path=tmp_path / "leadfinder.db")
    assert "AIza" not in text
    assert "gsk_" not in text
    assert "AIzaSyTESTNOTAREALKEY99" not in text
    assert "Google Places configured: yes" in text
    assert "Groq configured: yes" in text
    assert "API keys: not included" in text
    assert str(Path.home()) not in text or "%USERPROFILE%" in text or "$HOME" in text


def test_qsettings_never_holds_keys(tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    ini = tmp_path / "settings.ini"
    settings = QSettings(str(ini), QSettings.Format.IniFormat)
    settings.setValue("onboarding_completed", True)
    settings.sync()
    raw = ini.read_text(encoding="utf-8")
    assert "AIza" not in raw
    assert "gsk_" not in raw
    assert "GOOGLE_MAPS_API_KEY" not in raw


def test_places_account_override_does_not_use_production_account(monkeypatch) -> None:
    backend = MemorySecretBackend()
    set_secret_backend_for_tests(backend)
    monkeypatch.setenv("LEADFINDER_KEYRING_ACCOUNT_PLACES", "google-places-api-packaged-qa")
    monkeypatch.delenv("LEADFINDER_TEST_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    save_secret("places", "qa-only-dummy")
    assert backend.get_password("LeadFinder", "google-places-api") is None
    found = lookup_places_key()
    assert found.source == SOURCE_KEYRING
    assert found.value == "qa-only-dummy"
    delete_secret("places")
    assert lookup_places_key().source == SOURCE_NONE


def test_groq_lookup_none(monkeypatch) -> None:
    set_secret_backend_for_tests(MemorySecretBackend())
    monkeypatch.delenv("LEADFINDER_TEST_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert lookup_groq_key().source == SOURCE_NONE
