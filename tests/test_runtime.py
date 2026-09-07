from __future__ import annotations

from pathlib import Path

from leadfinder.desktop.identity import APP_DISPLAY_NAME, ORGANIZATION_NAME, application_version
from leadfinder.desktop.runtime import (
    application_root,
    is_frozen,
    resource_path,
    smoke_exit_requested,
)
from leadfinder.paths import path_is_under_install_dir, runtime_must_not_write_install_dir


def test_identity_matches_qsettings_names() -> None:
    assert APP_DISPLAY_NAME == "LeadFinder"
    assert ORGANIZATION_NAME == "LeadFinder"
    assert application_version() == "1.3.0"


def test_dev_runtime_is_not_frozen() -> None:
    assert is_frozen() is False
    assert application_root().name == "leadfinder"
    icon = resource_path("desktop", "assets", "leadfinder.ico")
    assert icon.parent.name == "assets"


def test_frozen_resource_path(monkeypatch, tmp_path: Path) -> None:
    from leadfinder.desktop import runtime

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "_MEIPASS", str(bundle), raising=False)
    assert runtime.is_frozen() is True
    assert runtime.application_root() == bundle
    assert runtime.resource_path("desktop", "assets", "leadfinder.ico") == bundle.joinpath(
        "desktop", "assets", "leadfinder.ico"
    )


def test_user_data_not_under_install_dir(monkeypatch, tmp_path: Path) -> None:
    from leadfinder import paths
    from leadfinder.desktop import runtime

    install = tmp_path / "Program Files" / "LeadFinder"
    install.mkdir(parents=True)
    user = tmp_path / "AppData" / "LeadFinder"
    user.mkdir(parents=True)
    monkeypatch.setattr(runtime, "is_frozen", lambda: True)
    monkeypatch.setattr(runtime, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "data_dir", lambda: user)
    assert path_is_under_install_dir(install / "LeadFinder.exe") is True
    assert path_is_under_install_dir(user / "leadfinder.db") is False
    assert runtime_must_not_write_install_dir() is True


def test_data_dir_override(monkeypatch, tmp_path: Path) -> None:
    from leadfinder import paths
    from leadfinder.desktop import runtime

    monkeypatch.setenv(runtime.DATA_DIR_ENV, str(tmp_path / "qa"))
    assert paths.data_dir() == tmp_path / "qa"
    assert paths.default_db_path() == tmp_path / "qa" / "leadfinder.db"
    assert paths.demo_db_path() == tmp_path / "qa" / "leadfinder-demo.db"
    assert paths.log_dir() == tmp_path / "qa" / "Logs"


def test_smoke_flag(monkeypatch) -> None:
    monkeypatch.delenv("LEADFINDER_SMOKE_EXIT", raising=False)
    assert smoke_exit_requested() is False
    monkeypatch.setenv("LEADFINDER_SMOKE_EXIT", "1")
    assert smoke_exit_requested() is True
