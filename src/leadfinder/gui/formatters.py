from __future__ import annotations

from datetime import datetime

from leadfinder.workflow import parse_utc


def format_when(value: str) -> str:
    parsed = parse_utc(value)
    if parsed is None:
        return "—"
    local = parsed.astimezone()
    today = datetime.now().astimezone().date()
    if local.date() == today:
        return f"Today {local.strftime('%H:%M')}"
    return local.strftime("%b %d %H:%M")
