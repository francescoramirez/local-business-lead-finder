# PyInstaller spec for LeadFinder Windows x64 one-folder GUI.
# Run via packaging/build_windows.ps1 so the package is importable.

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from leadfinder import __version__  # noqa: E402

APP_NAME = "LeadFinder"
ICON = SRC / "leadfinder" / "desktop" / "assets" / "leadfinder.ico"
LICENSE_FILE = ROOT / "LICENSE"
VERSION_FILE = ROOT / "packaging" / "file_version_info.txt"

datas: list = []
binaries: list = []
assets = SRC / "leadfinder" / "desktop" / "assets"
if assets.is_dir():
    for item in assets.iterdir():
        if item.is_file() and item.suffix.lower() in {".ico", ".png", ".py"}:
            datas.append((str(item), "desktop/assets"))
            datas.append((str(item), "leadfinder/desktop/assets"))
if LICENSE_FILE.is_file():
    datas.append((str(LICENSE_FILE), "."))

hiddenimports = [
    name
    for name in collect_submodules("leadfinder")
    if name not in {"leadfinder.cli", "leadfinder.__main__"}
    and not name.startswith("leadfinder.cli.")
]
hiddenimports += [
    "keyring.backends.Windows",
    "keyring.backends.macOS",
    "keyring.backends.SecretService",
    "keyring.backends.chainer",
    "keyring.backends.fail",
    "keyring.backends.null",
    "platformdirs",
    "dotenv",
    "zoneinfo",
    "tzdata",
]
try:
    from PyInstaller.utils.hooks import collect_all

    tz_datas, tz_binaries, tz_hidden = collect_all("tzdata")
    datas += tz_datas
    binaries += tz_binaries
    hiddenimports += tz_hidden
except Exception:
    pass

a = Analysis(
    [str(SRC / "leadfinder" / "desktop" / "launch.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "playwright"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(ICON) if ICON.is_file() else None,
    version=str(VERSION_FILE) if VERSION_FILE.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
