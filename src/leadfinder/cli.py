from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from leadfinder import __version__
from leadfinder.config import SearchConfig, get_api_key, parse_locations
from leadfinder.digital_presence import PresenceAnalyzer, format_presence_report
from leadfinder.errors import ConfigError, GuiDependencyError, LeadFinderError
from leadfinder.models import SearchPlan, SearchReport, utc_now_iso
from leadfinder.places_client import PlacesClient
from leadfinder.presets import list_presets
from leadfinder.search import build_plan, export_report, run_search

app = typer.Typer(
    name="leadfinder",
    help="Discover and prioritize local business leads with Google Places API (New).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)

BusinessArg = Annotated[
    str, typer.Option("--business", "-b", help="Business preset such as cafe or hotel.")
]
LocationArg = Annotated[
    list[str] | None,
    typer.Option("--location", "-l", help="Locality. Repeat or comma-separate."),
]
RegionArg = Annotated[
    str, typer.Option("--region", "-r", help="Region or province, for example Buenos Aires.")
]
CountryArg = Annotated[str, typer.Option("--country", "-c", help="ISO country code.")]
CoverageArg = Annotated[
    str, typer.Option("--coverage", help="Search breadth: budget, balanced, or full.")
]
FieldsArg = Annotated[
    str, typer.Option("--fields", help="Field mask: essentials, pro, or enterprise.")
]
TermArg = Annotated[
    list[str] | None,
    typer.Option("--term", "-t", help="Override preset keywords. Repeat or comma-separate."),
]
PlaceTypeArg = Annotated[
    str, typer.Option("--place-type", help="Places Table A includedType. Default: preset.")
]
GeoPresetArg = Annotated[
    str, typer.Option("--geo-preset", help="Optional location pack. Currently: buenos-aires.")
]
PageSizeArg = Annotated[int, typer.Option("--page-size", help="Results per page. API max is 20.")]
PagesArg = Annotated[int, typer.Option("--pages", help="Pages per query. Useful max is 3.")]
MaxRequestsArg = Annotated[int, typer.Option("--max-requests", help="Safety cap on API requests.")]
DelayArg = Annotated[float, typer.Option("--delay", help="Pause in seconds between queries.")]
LanguageArg = Annotated[str, typer.Option("--language", help="Places languageCode override.")]
OnlyNoWebsiteArg = Annotated[
    bool, typer.Option("--only-no-website", help="Export only businesses without a website.")
]
IncludeClosedArg = Annotated[
    bool, typer.Option("--include-closed", help="Keep CLOSED_PERMANENTLY results.")
]
AnalyzeArg = Annotated[
    bool, typer.Option("--analyze-websites", help="Classify listed URLs without crawling.")
]
OutputArg = Annotated[Path | None, typer.Option("--output", "-o", help="Output file path.")]
FormatArg = Annotated[str, typer.Option("--format", help="csv, json, or both.")]
ForceArg = Annotated[bool, typer.Option("--force", help="Overwrite an existing output file.")]
SeenIdsArg = Annotated[
    Path | None, typer.Option("--seen-ids", help="JSON file that stores Place IDs only.")
]
TestArg = Annotated[bool, typer.Option("--test", help="Cheap single-location smoke search.")]


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"leadfinder {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Local Business Lead Finder."""


def _build_config(
    business: str,
    location: list[str] | None,
    region: str,
    country: str,
    coverage: str,
    fields: str,
    term: list[str] | None,
    place_type: str,
    geo_preset: str,
    page_size: int,
    pages: int,
    max_requests: int,
    delay: float,
    language: str,
    only_no_website: bool,
    include_closed: bool,
    analyze_websites: bool,
    output: Path | None,
    format_name: str,
    force: bool,
    seen_ids: Path | None,
    test: bool,
) -> SearchConfig:
    locations = parse_locations(*(location or []))
    if test and not locations and not geo_preset:
        locations = ["Mar del Plata"]
    formats = ("csv", "json") if format_name == "both" else (format_name,)
    return SearchConfig(
        business=business,
        locations=locations,
        region=region,
        country=country,
        coverage="budget" if test else coverage,
        field_profile=fields,
        terms=parse_locations(*(term or [])),
        place_type=place_type,
        geo_preset=geo_preset,
        page_size=page_size,
        pages=1 if test else pages,
        max_requests=max_requests,
        delay=delay,
        language_code=language,
        only_no_website=only_no_website,
        include_closed=include_closed,
        analyze_websites=analyze_websites,
        output=output,
        formats=formats,
        force=force,
        seen_ids_path=seen_ids,
    )


def _print_plan(plan: SearchPlan) -> None:
    table = Table(title="Dry run", show_header=True, header_style="bold")
    table.add_column("Item")
    table.add_column("Value")
    rows = [
        ("Business preset", plan.business),
        ("Search terms", ", ".join(plan.search_terms)),
        ("Locations", str(len(plan.locations))),
        ("Country", plan.country),
        ("Region", plan.region or "(none)"),
        ("Coverage", plan.coverage),
        ("Max queries", str(plan.max_queries)),
        ("Max API requests", str(plan.max_api_requests)),
        ("Page size", str(plan.page_size)),
        ("Pages", str(plan.pages)),
        ("Field profile", plan.field_profile),
        ("Billing tier", plan.billing_tier),
        ("includedType", plan.included_type or "(none)"),
        ("Language", plan.language_code),
        ("Only no website", "yes" if plan.only_no_website else "no"),
        ("Include closed", "yes" if plan.include_closed else "no"),
        ("Analyze websites", "yes" if plan.analyze_websites else "no"),
    ]
    for label, value in rows:
        table.add_row(label, value)
    console.print(table)
    console.print("Locations:")
    for location in plan.locations:
        console.print(f"  - {location}")
    console.print(
        "\nNo API requests were made. Data from Google Maps, if fetched later, must be attributed."
    )


def _print_summary(report: SearchReport) -> None:
    table = Table(title="Search summary", show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Queries executed", str(report.queries_executed))
    table.add_row("API requests", str(report.api_requests))
    table.add_row("In-run cache hits", str(report.cache_hits))
    table.add_row("Places found", str(report.places_found))
    table.add_row("Duplicates discarded", str(report.duplicates_discarded))
    table.add_row("Operational leads", str(report.operational))
    table.add_row("Leads without website", str(report.no_website))
    table.add_row("Contactable leads", str(report.contactable))
    table.add_row("Leads exported", str(len(report.leads)))
    table.add_row("Output", ", ".join(report.output_paths) or "(none)")
    console.print(table)
    console.print("Place data is from Google Maps. See README compliance notes.")


@app.command("analyze")
def analyze_command(url: Annotated[str, typer.Argument(help="Website URL to classify.")]) -> None:
    """Classify a single URL's digital presence. No crawling, no JavaScript."""
    try:
        if not url.strip():
            raise ConfigError("Pass a website URL to analyze.")
        result = PresenceAnalyzer().analyze(url)
        console.print(format_presence_report(result))
    except LeadFinderError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


@app.command("presets")
def presets_command() -> None:
    """List built-in business presets."""
    table = Table(title="Business presets", show_header=True, header_style="bold")
    table.add_column("Preset")
    table.add_column("includedType")
    table.add_column("Budget terms")
    table.add_column("Description")
    for preset in list_presets():
        table.add_row(
            preset.name,
            preset.included_type or "(none)",
            ", ".join(preset.budget_terms),
            preset.description,
        )
    console.print(table)


@app.command("dry-run")
def dry_run_command(
    business: BusinessArg = "hotel",
    location: LocationArg = None,
    region: RegionArg = "",
    country: CountryArg = "AR",
    coverage: CoverageArg = "budget",
    fields: FieldsArg = "enterprise",
    term: TermArg = None,
    place_type: PlaceTypeArg = "",
    geo_preset: GeoPresetArg = "",
    page_size: PageSizeArg = 20,
    pages: PagesArg = 1,
    max_requests: MaxRequestsArg = 100,
    delay: DelayArg = 1.0,
    language: LanguageArg = "",
    only_no_website: OnlyNoWebsiteArg = False,
    include_closed: IncludeClosedArg = False,
    analyze_websites: AnalyzeArg = False,
    output: OutputArg = None,
    format_name: FormatArg = "csv",
    force: ForceArg = False,
    seen_ids: SeenIdsArg = None,
    test: TestArg = False,
) -> None:
    """Show the search plan and estimated request volume without calling Google."""
    try:
        config = _build_config(
            business,
            location,
            region,
            country,
            coverage,
            fields,
            term,
            place_type,
            geo_preset,
            page_size,
            pages,
            max_requests,
            delay,
            language,
            only_no_website,
            include_closed,
            analyze_websites,
            output,
            format_name,
            force,
            seen_ids,
            test,
        )
        _print_plan(build_plan(config))
    except LeadFinderError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


@app.command("search")
def search_command(
    business: BusinessArg = "hotel",
    location: LocationArg = None,
    region: RegionArg = "",
    country: CountryArg = "AR",
    coverage: CoverageArg = "budget",
    fields: FieldsArg = "enterprise",
    term: TermArg = None,
    place_type: PlaceTypeArg = "",
    geo_preset: GeoPresetArg = "",
    page_size: PageSizeArg = 20,
    pages: PagesArg = 1,
    max_requests: MaxRequestsArg = 100,
    delay: DelayArg = 1.0,
    language: LanguageArg = "",
    only_no_website: OnlyNoWebsiteArg = False,
    include_closed: IncludeClosedArg = False,
    analyze_websites: AnalyzeArg = False,
    output: OutputArg = None,
    format_name: FormatArg = "csv",
    force: ForceArg = False,
    seen_ids: SeenIdsArg = None,
    test: TestArg = False,
) -> None:
    """Search Google Places and export scored leads."""
    try:
        config = _build_config(
            business,
            location,
            region,
            country,
            coverage,
            fields,
            term,
            place_type,
            geo_preset,
            page_size,
            pages,
            max_requests,
            delay,
            language,
            only_no_website,
            include_closed,
            analyze_websites,
            output,
            format_name,
            force,
            seen_ids,
            test,
        )
        plan = build_plan(config)
        api_key = get_api_key()
        console.print(
            f"Searching {plan.business} in {len(plan.locations)} location(s) "
            f"({plan.billing_tier})."
        )
        client = PlacesClient(api_key)
        report = run_search(
            config,
            client,
            progress=lambda message: console.print(f"[dim]{message}[/dim]"),
        )
        export_report(report, config, utc_now_iso().replace(":", "").replace("-", "")[:15])
        _print_summary(report)
    except LeadFinderError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


@app.command("gui")
def gui_command() -> None:
    """Open the desktop application."""
    try:
        from leadfinder.gui.app import run_gui
    except GuiDependencyError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    try:
        raise typer.Exit(run_gui())
    except GuiDependencyError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
