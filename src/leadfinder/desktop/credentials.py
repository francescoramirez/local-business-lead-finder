"""API key resolution: test override, environment, then OS credential store.

Never persist secrets in SQLite, QSettings, workspace ZIP, logs, or JSON.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv

from leadfinder.desktop.runtime import install_dir, is_frozen
from leadfinder.errors import CredentialStoreError, MissingApiKeyError

LOGGER = logging.getLogger("leadfinder")

PLACES_ENV_VARS = ("GOOGLE_MAPS_API_KEY", "GOOGLE_PLACES_API_KEY")
GROQ_ENV_VAR = "GROQ_API_KEY"
TEST_PLACES_ENV = "LEADFINDER_TEST_PLACES_API_KEY"
TEST_GROQ_ENV = "LEADFINDER_TEST_GROQ_API_KEY"
KEYRING_SERVICE = "LeadFinder"
PLACES_ACCOUNT = "google-places-api"
GROQ_ACCOUNT = "groq-api"
KEYRING_ACCOUNT_PLACES_ENV = "LEADFINDER_KEYRING_ACCOUNT_PLACES"

SOURCE_TEST = "test"
SOURCE_ENVIRONMENT = "environment"
SOURCE_KEYRING = "keyring"
SOURCE_NONE = "none"


class SecretBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...

    def set_password(self, service: str, username: str, password: str) -> None: ...

    def delete_password(self, service: str, username: str) -> None: ...


@dataclass(frozen=True)
class SecretLookup:
    value: str
    source: str


_test_backend: SecretBackend | None = None


def set_secret_backend_for_tests(backend: SecretBackend | None) -> None:
    """Replace the OS store in-process. Tests only."""
    global _test_backend
    _test_backend = backend


class MemorySecretBackend:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._data.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._data[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._data.pop((service, username), None)


def load_env_file() -> None:
    """Load a developer .env from the current working directory.

    Frozen installs do not load `.env` from the install directory. Keys next to
    LeadFinder.exe would be plaintext in a writable-or-shared folder.
    Pytest never loads `.env` so developer secrets cannot leak into tests.
    """
    if os.getenv("LEADFINDER_IGNORE_DOTENV", "").strip() == "1":
        return
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    candidate = Path.cwd() / ".env"
    if not candidate.is_file():
        return
    installed = install_dir()
    if is_frozen() and installed is not None:
        try:
            if candidate.resolve().parent == installed.resolve():
                return
        except OSError:
            return
    load_dotenv(dotenv_path=candidate, override=False)


def keyring_available() -> bool:
    if _test_backend is not None:
        return True
    try:
        import keyring
    except ImportError:
        return False
    try:
        backend = keyring.get_keyring()
    except Exception:
        return False
    name = type(backend).__name__.lower()
    return "fail" not in name and "null" not in name


def _os_backend() -> SecretBackend | None:
    if _test_backend is not None:
        return _test_backend
    if not keyring_available():
        return None
    import keyring

    return keyring


def _env_first(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _from_store(account: str) -> str:
    backend = _os_backend()
    if backend is None:
        return ""
    try:
        value = backend.get_password(KEYRING_SERVICE, account)
    except Exception:
        LOGGER.info("OS credential store is unavailable for this lookup.")
        return ""
    if not value:
        return ""
    return str(value).strip()


def lookup_places_key() -> SecretLookup:
    load_env_file()
    test = os.getenv(TEST_PLACES_ENV, "").strip()
    if test:
        return SecretLookup(test, SOURCE_TEST)
    env = _env_first(PLACES_ENV_VARS)
    if env:
        return SecretLookup(env, SOURCE_ENVIRONMENT)
    stored = _from_store(places_account())
    if stored:
        return SecretLookup(stored, SOURCE_KEYRING)
    return SecretLookup("", SOURCE_NONE)


def lookup_groq_key() -> SecretLookup:
    load_env_file()
    test = os.getenv(TEST_GROQ_ENV, "").strip()
    if test:
        return SecretLookup(test, SOURCE_TEST)
    env = os.getenv(GROQ_ENV_VAR, "").strip()
    if env:
        return SecretLookup(env, SOURCE_ENVIRONMENT)
    stored = _from_store(GROQ_ACCOUNT)
    if stored:
        return SecretLookup(stored, SOURCE_KEYRING)
    return SecretLookup("", SOURCE_NONE)


def places_key_configured() -> bool:
    return bool(lookup_places_key().value)


def groq_key_configured() -> bool:
    return bool(lookup_groq_key().value)


def get_places_api_key() -> str:
    found = lookup_places_key()
    if found.value:
        return found.value
    raise MissingApiKeyError(
        "Missing Places API key. Set GOOGLE_MAPS_API_KEY or GOOGLE_PLACES_API_KEY "
        "in the environment, or save it in Settings using the OS credential store."
    )


def get_groq_api_key() -> str:
    return lookup_groq_key().value


def save_secret(kind: str, value: str) -> None:
    cleaned = value.strip()
    if not cleaned:
        raise CredentialStoreError("Cannot save an empty API key.")
    backend = _os_backend()
    if backend is None:
        raise CredentialStoreError(
            "OS credential storage is not available. Set the key in the environment instead."
        )
    account = _account_for(kind)
    try:
        backend.set_password(KEYRING_SERVICE, account, cleaned)
    except Exception as error:
        LOGGER.info("Could not save a credential to the OS store.")
        raise CredentialStoreError(
            "Could not save the key to the OS credential store."
        ) from error


def delete_secret(kind: str) -> None:
    backend = _os_backend()
    if backend is None:
        raise CredentialStoreError(
            "OS credential storage is not available. Environment variables cannot "
            "be removed from this dialog."
        )
    account = _account_for(kind)
    try:
        backend.delete_password(KEYRING_SERVICE, account)
    except Exception as error:
        message = str(error).lower()
        if "not found" in message or "could not be found" in message:
            return
        LOGGER.info("Could not remove a credential from the OS store.")
        raise CredentialStoreError(
            "Could not remove the key from the OS credential store."
        ) from error


def places_account() -> str:
    custom = os.getenv(KEYRING_ACCOUNT_PLACES_ENV, "").strip()
    return custom or PLACES_ACCOUNT


def _account_for(kind: str) -> str:
    key = kind.strip().lower()
    if key in {"places", "google", "google-places"}:
        return places_account()
    if key == "groq":
        return GROQ_ACCOUNT
    raise CredentialStoreError(f"Unknown credential kind '{kind}'.")
