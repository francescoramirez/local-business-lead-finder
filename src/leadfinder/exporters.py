from __future__ import annotations

import csv
import json
from pathlib import Path

from leadfinder.errors import ExportError
from leadfinder.models import EXPORT_COLUMNS, Lead, ManagedLead


def default_output_path(fmt: str, stamp: str) -> Path:
    return Path("output") / f"leads-{stamp}.{fmt}"


def ensure_output_path(path: Path, *, force: bool) -> Path:
    if path.exists() and not force:
        raise ExportError(
            f"{path} already exists. Pass --force to overwrite, "
            "or omit --output to use a timestamped file."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_csv(leads: list[Lead], path: Path, *, force: bool = False) -> Path:
    target = ensure_output_path(path, force=force)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EXPORT_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead.to_row())
    return target


def write_json(leads: list[Lead], path: Path, *, force: bool = False) -> Path:
    target = ensure_output_path(path, force=force)
    payload = [lead.to_row() for lead in leads]
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


def export_leads(
    leads: list[Lead],
    *,
    output: Path | None,
    formats: tuple[str, ...],
    stamp: str,
    force: bool = False,
) -> list[Path]:
    written: list[Path] = []
    for fmt in formats:
        if output is None:
            path = default_output_path(fmt, stamp)
        elif len(formats) == 1:
            path = output
        else:
            path = output.with_suffix(f".{fmt}")
        if fmt == "csv":
            written.append(write_csv(leads, path, force=force))
        elif fmt == "json":
            written.append(write_json(leads, path, force=force))
        else:
            raise ExportError(f"Unsupported export format: {fmt}")
    return written


PIPELINE_COLUMNS: tuple[str, ...] = (
    "place_id",
    "name",
    "contact_status",
    "next_follow_up_at",
    "tags",
    "notes",
    "last_contacted_at",
    "first_seen_at",
    "last_seen_at",
    "opportunity_score",
    "opportunity_level",
)


def pipeline_row(item: ManagedLead) -> dict[str, object]:
    return {
        "place_id": item.lead.place_id,
        "name": item.lead.name or item.label,
        "contact_status": item.contact_status,
        "next_follow_up_at": item.next_follow_up_at,
        "tags": item.tags,
        "notes": item.notes,
        "last_contacted_at": item.last_contacted_at,
        "first_seen_at": item.first_seen_at,
        "last_seen_at": item.last_seen_at,
        "opportunity_score": item.lead.opportunity_score,
        "opportunity_level": item.lead.opportunity_level,
    }


def write_pipeline_csv(items: list[ManagedLead], path: Path, *, force: bool = False) -> Path:
    target = ensure_output_path(path, force=force)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PIPELINE_COLUMNS))
        writer.writeheader()
        for item in items:
            writer.writerow(pipeline_row(item))
    return target


def write_activities_json(
    payload: list[dict[str, object]], path: Path, *, force: bool = False
) -> Path:
    target = ensure_output_path(path, force=force)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target
