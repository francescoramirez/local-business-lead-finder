"""Write a Windows VERSIONINFO resource for PyInstaller."""

from __future__ import annotations

import argparse
from pathlib import Path

from leadfinder import __version__
from leadfinder.desktop.identity import PRODUCT_NAME, PUBLISHER


def _tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(item) for item in version.split(".") if item.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    return parts[0], parts[1], parts[2], parts[3]


def render(version: str) -> str:
    major, minor, patch, build = _tuple(version)
    comma = f"{major}, {minor}, {patch}, {build}"
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({comma}),
    prodvers=({comma}),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [
        StringStruct('CompanyName', '{PUBLISHER}'),
        StringStruct('FileDescription', '{PRODUCT_NAME}'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', '{PRODUCT_NAME}'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026 {PUBLISHER}'),
        StringStruct('OriginalFilename', 'LeadFinder.exe'),
        StringStruct('ProductName', '{PRODUCT_NAME}'),
        StringStruct('ProductVersion', '{version}')
        ])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(render(__version__), encoding="utf-8")


if __name__ == "__main__":
    main()
