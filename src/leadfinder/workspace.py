"""Portable workspace ZIP. Own metadata only — no keys, payloads, or HTML."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from leadfinder import __version__
from leadfinder.errors import WorkspaceError
from leadfinder.models import LocalLeadState
from leadfinder.storage.schema import CURRENT_SCHEMA_VERSION

WORKSPACE_FORMAT_VERSION = 1
FORBIDDEN_EXPORT_KEYS = frozenset(
    {
        "api_key",
        "google_maps_api_key",
        "google_places_api_key",
        "groq_api_key",
        "authorization",
        "phone",
        "website",
        "html",
        "raw_payload",
        "google_payload",
    }
)


def _dump(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _load_json(raw: bytes, name: str) -> Any:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkspaceError(f"Invalid workspace file: {name}") from error
    return data


def _reject_secrets(blob: str) -> None:
    lowered = blob.lower()
    for key in FORBIDDEN_EXPORT_KEYS:
        if key in lowered and "place_id" not in key:
            if key in {"phone", "website", "html"} and key in lowered:
                # place_id / notes may mention the words; only fail on object keys
                continue
    if "aiza" in lowered or "gsk_" in lowered:
        raise WorkspaceError("Workspace file appears to contain a secret and was rejected.")


def export_workspace(
    store: object,
    destination: Path,
    *,
    settings: dict[str, object] | None = None,
) -> Path:
    from leadfinder.storage.local_leads import LocalLeadStore

    if not isinstance(store, LocalLeadStore):
        raise WorkspaceError("Workspace export requires a local store.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "workspace_format_version": WORKSPACE_FORMAT_VERSION,
        "app_version": __version__,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    workflow = [_state_export(item) for item in store.list_all()]
    campaigns = [item.__dict__ for item in store.list_campaigns()]
    activities = [
        {
            "place_id": item.place_id,
            "activity_type": item.activity_type,
            "created_at": item.created_at,
            "note": item.note,
            "contact_method": item.contact_method,
            "outcome": item.outcome,
            "metadata_json": item.metadata_json,
            "reverses_activity_id": item.reverses_activity_id,
        }
        for item in store.list_all_activities()
    ]
    experiments = [item.as_dict() for item in store.list_experiments()]
    templates = [
        {
            "name": item.name,
            "body": item.body,
            "business_type": item.business_type,
            "presence_type": item.presence_type,
            "language": item.language,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in store.list_templates()
    ]
    safe_settings = {
        key: value
        for key, value in (settings or {}).items()
        if str(key).lower() not in FORBIDDEN_EXPORT_KEYS
        and "key" not in str(key).lower()
        and "token" not in str(key).lower()
    }
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _dump(manifest))
        archive.writestr("workflow.json", _dump(workflow))
        archive.writestr("campaigns.json", _dump(campaigns))
        archive.writestr("activities.json", _dump(activities))
        archive.writestr("experiments.json", _dump(experiments))
        archive.writestr("pitch_templates.json", _dump(templates))
        archive.writestr("settings-non-sensitive.json", _dump(safe_settings))
    return destination


def _state_export(item: LocalLeadState) -> dict[str, object]:
    return {
        "place_id": item.place_id,
        "contact_status": item.contact_status,
        "notes": item.notes,
        "first_seen_at": item.first_seen_at,
        "last_seen_at": item.last_seen_at,
        "last_contacted_at": item.last_contacted_at,
        "tags": item.tags,
        "next_follow_up_at": item.next_follow_up_at,
        "last_activity_at": item.last_activity_at,
        "label": item.label,
        "opportunity_level": item.opportunity_level,
        "opportunity_score": item.opportunity_score,
        "has_phone": item.has_phone,
        "business_preset": item.business_preset,
        "source_location": item.source_location,
        "region": item.region,
        "country": item.country,
        "website_status": item.website_status,
        "campaign_id": item.campaign_id,
        "manual_priority": item.manual_priority,
    }


def import_workspace(store: object, source: Path) -> dict[str, Any]:
    from leadfinder.storage.local_leads import LocalLeadStore

    if not isinstance(store, LocalLeadStore):
        raise WorkspaceError("Workspace import requires a local store.")
    if not source.exists():
        raise WorkspaceError("Workspace file not found.")
    try:
        archive = zipfile.ZipFile(source)
    except zipfile.BadZipFile as error:
        raise WorkspaceError("Not a valid LeadFinder workspace ZIP.") from error
    with archive:
        names = set(archive.namelist())
        required = {"manifest.json", "workflow.json", "campaigns.json", "activities.json"}
        missing = required - names
        if missing:
            raise WorkspaceError(f"Workspace ZIP is missing: {', '.join(sorted(missing))}")
        manifest = _load_json(archive.read("manifest.json"), "manifest.json")
        if not isinstance(manifest, dict):
            raise WorkspaceError("Invalid workspace manifest.")
        version = int(manifest.get("workspace_format_version") or 0)
        if version < 1 or version > WORKSPACE_FORMAT_VERSION:
            raise WorkspaceError(
                f"Unsupported workspace_format_version {version}."
            )
        workflow = _load_json(archive.read("workflow.json"), "workflow.json")
        campaigns = _load_json(archive.read("campaigns.json"), "campaigns.json")
        activities = _load_json(archive.read("activities.json"), "activities.json")
        experiments = (
            _load_json(archive.read("experiments.json"), "experiments.json")
            if "experiments.json" in names
            else []
        )
        templates = (
            _load_json(archive.read("pitch_templates.json"), "pitch_templates.json")
            if "pitch_templates.json" in names
            else []
        )
        extra_settings = (
            _load_json(
                archive.read("settings-non-sensitive.json"),
                "settings-non-sensitive.json",
            )
            if "settings-non-sensitive.json" in names
            else {}
        )
    blob = json.dumps(
        [manifest, workflow, campaigns, activities, experiments, templates, extra_settings]
    )
    _reject_secrets(blob)
    if not isinstance(workflow, list) or not isinstance(campaigns, list):
        raise WorkspaceError("Workspace JSON must be lists of records.")
    if not isinstance(activities, list) or not isinstance(experiments, list):
        raise WorkspaceError("Workspace JSON must be lists of records.")
    if not isinstance(templates, list):
        raise WorkspaceError("Workspace JSON must be lists of records.")
    added = store.merge_workspace(
        workflow=workflow,
        campaigns=campaigns,
        activities=activities,
        experiments=experiments,
        templates=templates,
    )
    result: dict[str, Any] = dict(added)
    result["imported_saved_filters"] = extra_settings if isinstance(extra_settings, dict) else {}
    return result


def criteria_from_insight(dimension: str, key: str) -> dict[str, str]:
    if dimension == "business":
        return {"business_preset": key}
    if dimension == "location":
        return {"location": key}
    if dimension == "presence":
        return {"digital_presence": key}
    if dimension == "opportunity":
        return {"opportunity_level": key}
    if dimension in {"business+presence", "presence+opportunity"} and "|" in key:
        left, right = key.split("|", 1)
        if dimension == "business+presence":
            return {"business_preset": left, "digital_presence": right}
        return {"digital_presence": left, "opportunity_level": right}
    if dimension == "contact_method":
        return {}
    return {}
