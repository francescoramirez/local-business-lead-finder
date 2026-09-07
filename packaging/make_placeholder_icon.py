"""Create the provisional LeadFinder icon (original geometry, not a trademark)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

SIZE = 32
TEAL = (15, 118, 110, 255)
INK = (255, 255, 255, 255)
AMBER = (245, 158, 11, 255)


def _pixel(x: int, y: int) -> tuple[int, int, int, int]:
    margin = 3
    if x < margin or y < margin or x >= SIZE - margin or y >= SIZE - margin:
        return (15, 23, 42, 255)
    # Letter-like L block — original, provisional mark.
    if 8 <= x <= 12 and 8 <= y <= 23:
        return INK
    if 8 <= x <= 22 and 20 <= y <= 23:
        return INK
    if 18 <= x <= 23 and 8 <= y <= 14:
        return AMBER
    return TEAL


def _rgba_rows() -> list[bytes]:
    rows = []
    for y in range(SIZE):
        rows.append(b"".join(bytes(_pixel(x, y)) for x in range(SIZE)))
    return rows


def write_png(path: Path) -> None:
    rows = _rgba_rows()
    raw = b"".join(b"\x00" + row for row in rows)
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    payload = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed)
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def write_ico(path: Path) -> None:
    # 32-bit BGRA bitmap, bottom-up, plus 1-bit AND mask.
    xor = bytearray()
    for y in range(SIZE - 1, -1, -1):
        for x in range(SIZE):
            r, g, b, a = _pixel(x, y)
            xor.extend((b, g, r, a))
    mask_row_bytes = ((SIZE + 31) // 32) * 4
    and_mask = bytes(mask_row_bytes * SIZE)
    dib = struct.pack(
        "<IIIHHIIIIII",
        40,
        SIZE,
        SIZE * 2,
        1,
        32,
        0,
        len(xor),
        0,
        0,
        0,
        0,
    )
    image = dib + bytes(xor) + and_mask
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", SIZE, SIZE, 0, 0, 1, 32, len(image), 6 + 16)
    path.write_bytes(header + entry + image)


def main() -> None:
    target_dir = Path(__file__).resolve().parents[1] / "src" / "leadfinder" / "desktop" / "assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    write_ico(target_dir / "leadfinder.ico")
    write_png(target_dir / "leadfinder.png")
    readme = target_dir / "README.md"
    readme.write_text(
        "Provisional original icon (teal square with a block L). Not a third-party mark.\n"
        "Replace leadfinder.ico and leadfinder.png before a public store listing.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
