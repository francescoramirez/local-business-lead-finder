"""Prospect pipeline rules. Pure functions; no SQLite and no widgets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class ContactStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    FOLLOW_UP = "follow_up"
    WON = "won"
    REJECTED = "rejected"
    DO_NOT_CONTACT = "do_not_contact"


CONTACT_STATUSES: tuple[str, ...] = tuple(item.value for item in ContactStatus)

CONTACT_STATUS_LABELS: dict[str, str] = {
    ContactStatus.NEW.value: "New",
    ContactStatus.CONTACTED.value: "Contacted",
    ContactStatus.INTERESTED.value: "Interested",
    ContactStatus.FOLLOW_UP.value: "Follow-up",
    ContactStatus.WON.value: "Won",
    ContactStatus.REJECTED.value: "Rejected",
    ContactStatus.DO_NOT_CONTACT.value: "Do not contact",
}

PIPELINE_COLUMNS: tuple[str, ...] = (
    ContactStatus.NEW.value,
    ContactStatus.CONTACTED.value,
    ContactStatus.INTERESTED.value,
    ContactStatus.FOLLOW_UP.value,
    ContactStatus.WON.value,
)

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        ContactStatus.WON.value,
        ContactStatus.REJECTED.value,
        ContactStatus.DO_NOT_CONTACT.value,
    }
)

MIN_CONVERSION_DENOMINATOR = 3


class ActivityType(str, Enum):
    CONTACT_ATTEMPT = "contact_attempt"
    REPLY = "reply"
    MEETING = "meeting"
    FOLLOW_UP = "follow_up"
    NOTE = "note"
    STATUS_CHANGE = "status_change"
    DISCOVERED = "discovered"
    SALES_PREP_SAVED = "sales_prep_saved"
    PRIORITY_CHANGE = "priority_change"


ACTIVITY_TYPE_LABELS: dict[str, str] = {
    ActivityType.CONTACT_ATTEMPT.value: "Contact attempt",
    ActivityType.REPLY.value: "Reply",
    ActivityType.MEETING.value: "Meeting",
    ActivityType.FOLLOW_UP.value: "Follow-up",
    ActivityType.NOTE.value: "Note",
    ActivityType.STATUS_CHANGE.value: "Status change",
    ActivityType.DISCOVERED.value: "Lead discovered",
    ActivityType.SALES_PREP_SAVED.value: "Sales prep saved",
    ActivityType.PRIORITY_CHANGE.value: "Priority change",
}

CONTACT_METHODS: tuple[str, ...] = (
    "phone",
    "email",
    "instagram",
    "whatsapp",
    "in_person",
    "other",
)

CONTACT_METHOD_LABELS: dict[str, str] = {
    "phone": "Phone",
    "email": "Email",
    "instagram": "Instagram",
    "whatsapp": "WhatsApp",
    "in_person": "In person",
    "other": "Other",
}

OUTCOMES: tuple[str, ...] = (
    "no_answer",
    "replied",
    "interested",
    "not_interested",
    "meeting_booked",
)

OUTCOME_LABELS: dict[str, str] = {
    "no_answer": "No answer",
    "replied": "Replied",
    "interested": "Interested",
    "not_interested": "Not interested",
    "meeting_booked": "Meeting booked",
}


def utc_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc, microsecond=0)
    return now.astimezone(timezone.utc).replace(microsecond=0)


def to_iso(value: datetime) -> str:
    return utc_now(value).isoformat()


def parse_utc(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def is_overdue(status: str, next_follow_up_at: str, *, now: datetime | None = None) -> bool:
    if is_terminal(status):
        return False
    due = parse_utc(next_follow_up_at)
    if due is None:
        return False
    return due < utc_now(now)


def is_due_today(status: str, next_follow_up_at: str, *, now: datetime | None = None) -> bool:
    if is_terminal(status):
        return False
    due = parse_utc(next_follow_up_at)
    if due is None:
        return False
    current = utc_now(now)
    local_tz = current.astimezone().tzinfo
    return due.astimezone(local_tz).date() == current.astimezone(local_tz).date()


def is_upcoming(status: str, next_follow_up_at: str, *, now: datetime | None = None) -> bool:
    if is_terminal(status):
        return False
    due = parse_utc(next_follow_up_at)
    if due is None:
        return False
    current = utc_now(now)
    return due >= current and not is_due_today(status, next_follow_up_at, now=current)


def has_follow_up(next_follow_up_at: str) -> bool:
    return bool(next_follow_up_at.strip())


def follow_up_bucket(
    status: str, next_follow_up_at: str, *, now: datetime | None = None
) -> str:
    if not has_follow_up(next_follow_up_at):
        return "none"
    if is_overdue(status, next_follow_up_at, now=now):
        return "overdue"
    if is_due_today(status, next_follow_up_at, now=now):
        return "due_today"
    if is_upcoming(status, next_follow_up_at, now=now):
        return "upcoming"
    return "none"


def matches_follow_up_view(
    status: str,
    next_follow_up_at: str,
    view: str,
    *,
    now: datetime | None = None,
) -> bool:
    if not view:
        return True
    bucket = follow_up_bucket(status, next_follow_up_at, now=now)
    if view == "needs":
        return has_follow_up(next_follow_up_at) and not is_terminal(status)
    if view == "none":
        return bucket == "none"
    return bucket == view


def shift_iso(days: int, *, now: datetime | None = None) -> str:
    return to_iso(utc_now(now) + timedelta(days=days))


def conversion_rate(numerator: int, denominator: int) -> float | None:
    if denominator < MIN_CONVERSION_DENOMINATOR:
        return None
    return round(100.0 * numerator / denominator, 1)


@dataclass(frozen=True)
class PipelineCounts:
    total: int
    new: int
    contacted: int
    interested: int
    follow_up: int
    won: int
    rejected: int
    do_not_contact: int
    overdue: int
    due_today: int
    high_opportunity: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "new": self.new,
            "contacted": self.contacted,
            "interested": self.interested,
            "follow_up": self.follow_up,
            "won": self.won,
            "rejected": self.rejected,
            "do_not_contact": self.do_not_contact,
            "overdue": self.overdue,
            "due_today": self.due_today,
            "high_opportunity": self.high_opportunity,
        }


def pipeline_counts(
    rows: list[tuple[str, str, str]],
    *,
    now: datetime | None = None,
    high_opportunity: int = 0,
) -> PipelineCounts:
    """rows: (status, next_follow_up_at, opportunity_level)."""
    tallies = {status: 0 for status in CONTACT_STATUSES}
    overdue = 0
    due_today = 0
    for status, follow_up, _level in rows:
        if status in tallies:
            tallies[status] += 1
        if is_overdue(status, follow_up, now=now):
            overdue += 1
        elif is_due_today(status, follow_up, now=now):
            due_today += 1
    high = high_opportunity
    if high == 0:
        high = sum(1 for _status, _follow, level in rows if level == "high")
    return PipelineCounts(
        total=len(rows),
        new=tallies[ContactStatus.NEW.value],
        contacted=tallies[ContactStatus.CONTACTED.value],
        interested=tallies[ContactStatus.INTERESTED.value],
        follow_up=tallies[ContactStatus.FOLLOW_UP.value],
        won=tallies[ContactStatus.WON.value],
        rejected=tallies[ContactStatus.REJECTED.value],
        do_not_contact=tallies[ContactStatus.DO_NOT_CONTACT.value],
        overdue=overdue,
        due_today=due_today,
        high_opportunity=high,
    )


def contacted_to_interested_rate(counts: PipelineCounts) -> float | None:
    reached = counts.contacted + counts.interested + counts.follow_up + counts.won
    advanced = counts.interested + counts.follow_up + counts.won
    return conversion_rate(advanced, reached)


def interested_to_won_rate(counts: PipelineCounts) -> float | None:
    pool = counts.interested + counts.follow_up + counts.won
    return conversion_rate(counts.won, pool)


def parse_tags(raw: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        tag = item.strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def join_tags(tags: list[str]) -> str:
    return ", ".join(parse_tags(",".join(tags)))
