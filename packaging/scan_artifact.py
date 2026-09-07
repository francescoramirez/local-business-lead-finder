"""Heuristic scan of a packaged folder. Not a security guarantee."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKIP_SUFFIXES = {".png", ".ico", ".dll", ".pyd", ".exe", ".so", ".qmlc", ".pyc", ".pyo"}
EXPECTED_ZIPS = {"base_library.zip"}
PLACEHOLDERS = (
    "your-places-api-key-here",
    "your-groq-api-key-here",
    "gsk_example",
)
FORBIDDEN_NAMES = {".env", "leadfinder.db", "leadfinder-demo.db", "credentials.json"}
FORBIDDEN_DIRS = {".git", "__pycache__", "tests"}
PATTERNS = (
    b"AIza",
    b"gsk_",
    b"GROQ_API_KEY=",
    b"GOOGLE_MAPS_API_KEY=",
    b"GOOGLE_PLACES_API_KEY=",
    b"LEADFINDER_TEST_PLACES_API_KEY=",
)
LEAK_NEEDLES = (
    b"C:\\Users\\franc",
    b"OneDrive",
    b"Documents\\GitHub",
    b"ScrapeNegocios",
)
TEXTISH = {".txt", ".md", ".json", ".xml", ".html", ".csv", ".iss", ".ps1", ".py", ".toml"}


def is_placeholder(chunk: bytes) -> bool:
    lowered = chunk.lower()
    return any(item.encode("ascii") in lowered for item in PLACEHOLDERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--leaks-report", default="")
    args = parser.parse_args()
    root = Path(args.root)
    if not root.is_dir():
        print(f"Missing artifact directory: {root}", file=sys.stderr)
        return 1
    failures: list[str] = []
    leaks: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_dir():
            if path.name in FORBIDDEN_DIRS:
                failures.append(f"forbidden directory: {rel}")
            continue
        forbidden_suffix = path.suffix.lower() in {".db", ".env", ".sqlite", ".log"}
        if path.name in FORBIDDEN_NAMES or forbidden_suffix:
            failures.append(f"forbidden file: {rel}")
            continue
        if path.suffix.lower() == ".zip" and path.name.lower() not in EXPECTED_ZIPS:
            failures.append(f"unexpected zip: {rel}")
            continue
        if any(part in FORBIDDEN_DIRS for part in rel.parts):
            failures.append(f"forbidden path: {rel}")
            continue
        small = path.stat().st_size <= 2_000_000
        inspect_leaks = path.suffix.lower() in TEXTISH or small
        under_cap = path.stat().st_size <= 5_000_000
        if inspect_leaks and path.suffix.lower() not in SKIP_SUFFIXES and under_cap:
            try:
                data = path.read_bytes()
            except OSError:
                data = b""
            for needle in LEAK_NEEDLES:
                if needle in data:
                    leaks.append(f"{needle.decode('ascii', 'replace')} in {rel}")
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.stat().st_size > 5_000_000:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for needle in PATTERNS:
            index = data.find(needle)
            if index < 0:
                continue
            window = data[max(0, index - 40) : index + 80]
            if is_placeholder(window):
                continue
            if needle.endswith(b"=") and b"your-" in window.lower():
                continue
            if needle in {
                b"GROQ_API_KEY=",
                b"GOOGLE_MAPS_API_KEY=",
                b"GOOGLE_PLACES_API_KEY=",
            } and (b"example" in window.lower() or b"optional" in window.lower()):
                continue
            failures.append(f"pattern {needle.decode('ascii', 'replace')} in {rel}")
    if args.leaks_report:
        Path(args.leaks_report).write_text(
            "\n".join(leaks) + ("\n" if leaks else "no text-asset source-path leaks\n"),
            encoding="utf-8",
        )
        print(f"Source-path leak notes: {len(leaks)} text-asset hit(s). See {args.leaks_report}")
    if failures:
        print("Artifact scan findings:", file=sys.stderr)
        for item in failures:
            print(f"  {item}", file=sys.stderr)
        return 1
    print("Artifact scan: no forbidden files or live-looking key prefixes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
