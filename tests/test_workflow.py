from __future__ import annotations

from datetime import datetime, timedelta, timezone

from leadfinder.workflow import (
    ContactStatus,
    conversion_rate,
    follow_up_bucket,
    interested_to_won_rate,
    is_due_today,
    is_overdue,
    is_upcoming,
    matches_follow_up_view,
    parse_tags,
    pipeline_counts,
)

NOW = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)


def test_contact_status_values_match_legacy_strings() -> None:
    assert ContactStatus.NEW.value == "new"
    assert ContactStatus.DO_NOT_CONTACT.value == "do_not_contact"


def test_overdue_and_due_today_and_upcoming() -> None:
    past = (NOW - timedelta(hours=2)).isoformat()
    later_today = (NOW + timedelta(hours=2)).isoformat()
    future = (NOW + timedelta(days=4)).isoformat()
    assert is_overdue("new", past, now=NOW)
    assert not is_overdue("won", past, now=NOW)
    assert not is_overdue("rejected", past, now=NOW)
    assert not is_overdue("new", "", now=NOW)
    assert is_due_today("new", later_today, now=NOW)
    assert is_upcoming("new", future, now=NOW)
    assert follow_up_bucket("new", past, now=NOW) == "overdue"
    assert matches_follow_up_view("new", past, "overdue", now=NOW)
    assert matches_follow_up_view("new", "", "none", now=NOW)
    assert matches_follow_up_view("new", past, "needs", now=NOW)


def test_pipeline_counts_and_conversion_guard() -> None:
    rows = [
        ("new", "", "high"),
        ("contacted", "", "medium"),
        ("contacted", "", "low"),
        ("interested", "", "high"),
        ("won", "", "high"),
    ]
    counts = pipeline_counts(rows, now=NOW)
    assert counts.total == 5
    assert counts.new == 1
    assert counts.high_opportunity == 3
    assert conversion_rate(1, 2) is None
    assert interested_to_won_rate(counts) is None


def test_parse_tags_dedupes() -> None:
    assert parse_tags("Priority, call, PRIORITY") == ["priority", "call"]
