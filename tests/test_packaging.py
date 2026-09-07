from __future__ import annotations

from pathlib import Path

from leadfinder import __version__


def test_spec_is_onedir_no_upx() -> None:
    spec = Path("packaging/leadfinder.spec").read_text(encoding="utf-8")
    assert "COLLECT(" in spec
    assert "upx=False" in spec
    assert "console=False" in spec
    assert "from leadfinder import __version__" in spec
    assert "launch.py" in spec
    assert "leadfinder.cli" in spec
    assert "tzdata" in spec
    assert "collect_all" in spec


def test_pyproject_version_sync() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in text
    assert "pyinstaller>=6.10.0,<7" in text
    assert "PySide6-Essentials>=6.6.0,<7" in text
    assert "tzdata" in text
    assert "keyring" in text


def test_version_info_renderer() -> None:
    import sys

    sys.path.insert(0, str(Path("packaging").resolve()))
    from write_version_info import render

    blob = render("1.3.0")
    assert "ProductName" in blob
    assert "1.3.0" in blob
    assert "LeadFinder.exe" in blob
    assert "FrancescoRamirezC" in blob


def test_icon_assets_exist() -> None:
    from leadfinder.desktop.assets import bundled_icon_path, icon_path

    # Generated during build; source tree may already include it after make_placeholder_icon.
    assert icon_path().parent.name == "assets"
    path = bundled_icon_path()
    assert path.name == "leadfinder.ico"
