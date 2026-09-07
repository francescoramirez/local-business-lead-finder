"""One-off binary path leak notes. Not a security proof."""

from __future__ import annotations

import sys
from pathlib import Path

NEEDLES = (
    b"C:\\Users\\franc",
    b"OneDrive",
    b"ScrapeNegocios",
    b"Documents\\GitHub",
)


def main() -> None:
    root = Path(sys.argv[1])
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 12_000_000:
            continue
        if path.suffix.lower() not in {".exe", ".pyd", ".dll", ".pyc", ".pyz"}:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for needle in NEEDLES:
            if needle in data:
                hits.append(f"{needle!r} in {path.relative_to(root)}")
                break
    print(f"binary_path_hits {len(hits)}")
    for item in hits[:40]:
        print(item)


if __name__ == "__main__":
    main()
