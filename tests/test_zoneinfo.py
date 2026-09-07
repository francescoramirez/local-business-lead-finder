from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from leadfinder.analytics import coerce_timezone


def test_analytics_timezones_resolve_to_zoneinfo() -> None:
    for name in ("America/Argentina/Buenos_Aires", "America/New_York", "UTC"):
        tz = coerce_timezone(name)
        assert isinstance(tz, ZoneInfo)
        datetime.now(tz)
