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


def write_analytics_json(report: object, path: Path, *, force: bool = False) -> Path:
    from leadfinder.analytics import AnalyticsReport

    target = ensure_output_path(path, force=force)
    payload = report.to_dict() if isinstance(report, AnalyticsReport) else report
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


def write_analytics_csv(report: object, path: Path, *, force: bool = False) -> Path:
    from leadfinder.analytics import AnalyticsReport, format_rate

    if not isinstance(report, AnalyticsReport):
        raise ExportError("Analytics CSV requires an AnalyticsReport.")
    target = ensure_output_path(path, force=force)
    rows: list[dict[str, object]] = []
    hist = report.historical
    snap = report.snapshot
    overview = [
        ("leads", hist.total_leads),
        ("contacted_once", hist.contacted_once),
        ("interested_once", hist.interested_once),
        ("won_once", hist.won_once),
        ("contact_rate", format_rate(report.contact_rate)),
        ("contact_to_interest", format_rate(report.contact_to_interest)),
        ("overdue_followups", snap.overdue_followups),
    ]
    for metric, value in overview:
        rows.append({"dimension": "overview", "segment": metric, "value": value})
    for name, table in (
        ("business", report.by_business),
        ("location", report.by_location),
        ("presence", report.by_presence),
        ("opportunity", report.by_opportunity),
    ):
        for row in table:
            rows.append(
                {
                    "dimension": name,
                    "segment": row.label,
                    "leads": row.leads,
                    "contacted": row.contacted,
                    "interested": row.interested,
                    "won": row.won,
                    "contact_to_interest": row.contact_to_interest,
                }
            )
    fieldnames = [
        "dimension",
        "segment",
        "value",
        "leads",
        "contacted",
        "interested",
        "won",
        "contact_to_interest",
    ]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return target


def write_analytics_markdown(report: object, path: Path, *, force: bool = False) -> Path:
    from leadfinder.analytics import AnalyticsReport, format_rate

    if not isinstance(report, AnalyticsReport):
        raise ExportError("Analytics Markdown requires an AnalyticsReport.")
    target = ensure_output_path(path, force=force)
    hist = report.historical
    lines = [
        "# Campaign Report",
        "",
        f"Period: {report.period_label}",
        f"Campaign: {report.campaign_name}",
        "",
        "## Overview",
        "",
        f"Leads: {hist.total_leads}",
        f"Contacted (once): {hist.contacted_once}",
        f"Interested (once): {hist.interested_once}",
        f"Won (once): {hist.won_once}",
        f"Contact rate: {format_rate(report.contact_rate)}",
        f"Contact→Interest: {format_rate(report.contact_to_interest)}",
        "",
        "Historical conversions count a lead if it reached a stage at least once.",
        "Rejected / do-not-contact without contact history are not counted as contacted.",
        "",
    ]
    if report.observations:
        lines.extend(["## Observations", ""])
        lines.extend(f"- {item}" for item in report.observations)
        lines.append("")
    if report.by_business:
        lines.extend(
            [
                "## Business type",
                "",
                "| Type | Leads | Contacted | Interested | Won |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in report.by_business:
            lines.append(
                f"| {row.label} | {row.leads} | {row.contacted} | {row.interested} | {row.won} |"
            )
        lines.append("")
    if report.ai_prep_saved:
        lines.extend(
            [
                "## AI sales prep (descriptive)",
                "",
                f"Leads where AI prep was saved: {report.ai_prep_saved}",
                f"Interested: {report.ai_prep_interested}",
                f"Won: {report.ai_prep_won}",
                "",
                "Correlation only — no causal claim.",
                "",
            ]
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def write_insights_json(report: object, path: Path, *, force: bool = False) -> Path:
    from leadfinder.insights import InsightsReport

    target = ensure_output_path(path, force=force)
    payload = report.to_dict() if isinstance(report, InsightsReport) else report
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


def write_insights_markdown(report: object, path: Path, *, force: bool = False) -> Path:
    from leadfinder.analytics import format_rate
    from leadfinder.insights import InsightsReport, format_segment_line

    if not isinstance(report, InsightsReport):
        raise ExportError("Insights Markdown requires an InsightsReport.")
    target = ensure_output_path(path, force=force)
    lines = [
        "# Outcome insights",
        "",
        f"Period: {report.period_label}",
        f"Campaign: {report.campaign_name}",
        "",
        "## Baseline",
        "",
        f"Contact->Interest: {format_rate(report.baseline)} (n={report.baseline.denominator})",
        "",
        "## Suggested experiment",
        "",
        report.suggested_experiment,
        "",
        "Differences are percentage points vs baseline, not relative percent.",
        "Unknown segments are not ranked. Small samples are omitted.",
        "",
    ]
    if report.strongest:
        lines.extend(
            [
                "## Strongest observed segment",
                "",
                format_segment_line(report.strongest),
                "",
            ]
        )
    if report.weakest:
        lines.extend(
            [
                "## Lower observed conversion",
                "",
                format_segment_line(report.weakest),
                "",
            ]
        )
    if report.ranked:
        lines.extend(["## Ranked segments", ""])
        for row in report.ranked:
            lines.append(format_segment_line(row, prefix="- "))
        lines.append("")
    if report.combinations:
        lines.extend(["## Two-dimension combinations", ""])
        for row in report.combinations:
            lines.append(format_segment_line(row, prefix="- "))
        lines.append("")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
