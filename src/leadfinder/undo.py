"""Pure undo rules. Never deletes activity history."""

from __future__ import annotations

from dataclasses import dataclass

from leadfinder.models import Activity, LocalLeadState

UNDOABLE_TYPES = frozenset({"status_change", "follow_up", "priority_change"})

FIELD_BY_TYPE = {
    "status_change": "contact_status",
    "follow_up": "next_follow_up_at",
    "priority_change": "manual_priority",
}


@dataclass(frozen=True)
class UndoPlan:
    activity: Activity
    field: str
    restore_value: str
    current_value: str


def parse_metadata(activity: Activity) -> dict[str, str]:
    raw = activity.metadata_json.strip()
    if not raw:
        return {}
    import json

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def current_field_value(state: LocalLeadState, field: str) -> str:
    return str(getattr(state, field, "") or "")


def already_reversed(activity: Activity, history: list[Activity]) -> bool:
    return any(item.reverses_activity_id == activity.id for item in history)


def can_undo(activity: Activity, state: LocalLeadState, history: list[Activity]) -> bool:
    if activity.activity_type not in UNDOABLE_TYPES:
        return False
    if already_reversed(activity, history):
        return False
    meta = parse_metadata(activity)
    previous = meta.get("previous_value")
    after = meta.get("new_value")
    if previous is None or after is None:
        return False
    field = FIELD_BY_TYPE[activity.activity_type]
    if current_field_value(state, field) != after:
        return False
    later = [item for item in history if item.id > activity.id]
    if any(item.activity_type in UNDOABLE_TYPES for item in later):
        return False
    return True


def latest_undoable(history: list[Activity], state: LocalLeadState) -> UndoPlan | None:
    ordered = sorted(history, key=lambda item: (item.created_at, item.id), reverse=True)
    for activity in ordered:
        if not can_undo(activity, state, history):
            continue
        meta = parse_metadata(activity)
        field = FIELD_BY_TYPE[activity.activity_type]
        return UndoPlan(
            activity=activity,
            field=field,
            restore_value=meta["previous_value"],
            current_value=meta["new_value"],
        )
    return None


def inverse_note(plan: UndoPlan) -> str:
    labels = {
        "contact_status": "Status",
        "next_follow_up_at": "Follow-up",
        "manual_priority": "Priority",
    }
    label = labels.get(plan.field, plan.field)
    return f"Undo: {label} {plan.current_value or '(empty)'} -> {plan.restore_value or '(empty)'}"
