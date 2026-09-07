"""Write dist/release/release-manifest.json and SHA256SUMS.txt."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from leadfinder import __version__


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def folder_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=__version__)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--installer", default="")
    parser.add_argument("--release-dir", default="dist/release")
    parser.add_argument("--python-version", default=platform.python_version())
    parser.add_argument("--pyinstaller-version", default="")
    parser.add_argument("--pyside-version", default="")
    parser.add_argument("--qt-version", default="")
    parser.add_argument("--installer-tool", default="not_available")
    args = parser.parse_args()
    app_dir = Path(args.app_dir)
    zip_path = Path(args.zip)
    installer = Path(args.installer) if args.installer else None
    release_dir = Path(args.release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)
    artifacts = []
    if zip_path.is_file():
        artifacts.append(
            {
                "filename": zip_path.name,
                "sha256": sha256(zip_path),
                "bytes": zip_path.stat().st_size,
            }
        )
    if installer is not None and installer.is_file():
        artifacts.append(
            {
                "filename": installer.name,
                "sha256": sha256(installer),
                "bytes": installer.stat().st_size,
            }
        )
    payload = {
        "version": args.version,
        "platform": "windows",
        "architecture": "x64",
        "python_version": args.python_version,
        "pyinstaller_version": args.pyinstaller_version or "unknown",
        "pyside_version": args.pyside_version or "unknown",
        "qt_version": args.qt_version or "unknown",
        "installer_tool": args.installer_tool,
        "packager": "pyinstaller-onedir",
        "upx": False,
        "code_signed": False,
        "build_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_folder": "dist/LeadFinder",
        "app_folder_bytes": folder_size(app_dir) if app_dir.is_dir() else 0,
        "artifacts": artifacts,
        "notes": (
            "Repeatable build process, not bit-for-bit reproducible. "
            "Unsigned. SmartScreen may warn for unsigned builds."
        ),
    }
    out = release_dir / "release-manifest.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    hashes = release_dir / "SHA256SUMS.txt"
    lines = [f"{item['sha256']}  {item['filename']}" for item in artifacts]
    hashes.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"Wrote {out.as_posix()}")


if __name__ == "__main__":
    main()
