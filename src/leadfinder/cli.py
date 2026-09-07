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
from leadfinder.logging_setup import configure_logging
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
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Debug logging to the console and rotating log file. Secrets are redacted.",
    ),
) -> None:
    """Local Business Lead Finder."""
    if verbose:
        configure_logging(verbose=True)


def _resolve_campaign_id(campaign: str) -> int | None:
    from leadfinder.application.service import LeadService

    if not campaign.strip():
        return None
    service = LeadService()
    matches = [
        item
        for item in service.campaigns()
        if item.name.lower() == campaign.strip().lower()
        or item.name.lower().startswith(campaign.strip().lower())
    ]
    if len(matches) != 1:
        err_console.print("[red]Campaign not found or name is not unique.[/red]")
        raise typer.Exit(code=1)
    return matches[0].id


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


def _print_plan(plan: SearchPlan, *, max_requests: int) -> None:
    from leadfinder.costs.estimator import estimate_plan, page_scenarios
    from leadfinder.costs.models import format_estimate

    table = Table(title="Dry run", show_header=True, header_style="bold")
    table.add_column("Item")
    table.add_column("Value")
    estimate = estimate_plan(plan)
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
        ("Billing SKU", estimate.billing_sku or plan.billing_tier),
        ("Estimated list cost", format_estimate(estimate).replace("Estimated list cost: ", "")),
        ("Pricing catalog", estimate.pricing_version),
    ]
    for label, value in rows:
        table.add_row(label, value)
    console.print(table)
    console.print("Page comparison (no network):")
    for pages, requests, cost in page_scenarios(
        query_count=plan.max_queries,
        max_requests=max_requests,
        field_profile=plan.field_profile,
    ):
        console.print(f"  {pages} page(s): {requests} requests · {format_estimate(cost)}")
    console.print("Locations:")
    for location in plan.locations:
        console.print(f"  - {location}")
    console.print(
        "\nNo API requests were made. Estimated list cost is not an invoice. "
        "Data from Google Maps, if fetched later, must be attributed."
    )


def _print_summary(report: SearchReport) -> None:
    table = Table(title="Search summary", show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Queries executed", str(report.queries_executed))
    table.add_row("Completed page requests", str(report.api_requests))
    table.add_row("HTTP attempts", str(report.http_attempts))
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
        _print_plan(build_plan(config), max_requests=config.max_requests)
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


@app.command("stats")
def stats_command() -> None:
    """Show local pipeline counts from the on-disk SQLite workspace."""
    from leadfinder.application.service import LeadService

    counts = LeadService().dashboard()
    table = Table(title="Local pipeline", show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for label, value in [
        ("New", counts.new),
        ("Contacted", counts.contacted),
        ("Interested", counts.interested),
        ("Follow-up", counts.follow_up),
        ("Won", counts.won),
        ("Rejected", counts.rejected),
        ("Do not contact", counts.do_not_contact),
        ("Overdue", counts.overdue),
        ("Due today", counts.due_today),
        ("Total", counts.total),
    ]:
        table.add_row(label, str(value))
    console.print(table)


@app.command("analytics")
def analytics_command(
    days: Annotated[int, typer.Option("--days", help="Lookback window. 0 = all time.")] = 30,
    campaign: Annotated[
        str,
        typer.Option("--campaign", help="Campaign name (exact or unique prefix)."),
    ] = "",
    output: OutputArg = None,
) -> None:
    """Show local campaign analytics. No network."""
    from leadfinder.analytics import format_rate
    from leadfinder.application.service import LeadService

    service = LeadService()
    campaign_id = _resolve_campaign_id(campaign)
    window_days = None if days <= 0 else days
    report = service.analytics_report(days=window_days, campaign_id=campaign_id)
    if output is not None:
        written = service.export_analytics(report, output)
        console.print(f"Report saved to {written}")
        return
    console.print(f"LeadFinder Analytics - {report.period_label}")
    console.print(f"Campaign: {report.campaign_name}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    hist = report.historical
    for label, value in [
        ("Leads", str(hist.total_leads)),
        ("Contacted", str(hist.contacted_once)),
        ("Interested", str(hist.interested_once)),
        ("Won", str(hist.won_once)),
        ("Contact rate", format_rate(report.contact_rate)),
        ("Contact->Interest", format_rate(report.contact_to_interest)),
        ("Contact->Win", format_rate(report.contact_to_win)),
        ("Interest->Win", format_rate(report.interest_to_win)),
    ]:
        table.add_row(label, value)
    console.print(table)


@app.command("insights")
def insights_command(
    days: Annotated[int, typer.Option("--days", help="Lookback window. 0 = all time.")] = 30,
    campaign: Annotated[
        str,
        typer.Option("--campaign", help="Campaign name (exact or unique prefix)."),
    ] = "",
    output: OutputArg = None,
) -> None:
    """Show outcome-driven segment insights. No network."""
    from leadfinder.analytics import format_rate
    from leadfinder.application.service import LeadService
    from leadfinder.insights import format_uplift

    service = LeadService()
    campaign_id = _resolve_campaign_id(campaign)
    window_days = None if days <= 0 else days
    report = service.insights_report(days=window_days, campaign_id=campaign_id)
    if output is not None:
        written = service.export_insights(report, output)
        console.print(f"Report saved to {written}")
        return
    console.print(f"LeadFinder Insights - {report.period_label}")
    console.print(f"Campaign: {report.campaign_name}")
    console.print(
        f"Overall contact->interest {format_rate(report.baseline)} "
        f"n={report.baseline.denominator}"
    )
    if report.empty:
        console.print(report.suggested_experiment)
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Segment")
    table.add_column("Rate", justify="right")
    table.add_column("vs baseline")
    table.add_column("n", justify="right")
    table.add_column("Confidence")
    for row in report.ranked[:12]:
        table.add_row(
            row.label,
            f"{row.rate}%",
            format_uplift(row.uplift_pp),
            str(row.n),
            row.confidence,
        )
    console.print(table)
    if report.strongest:
        console.print(
            f"Strongest observed: {report.strongest.label} "
            f"{report.strongest.rate}% n={report.strongest.n}"
        )
    if report.weakest:
        console.print(
            f"Lower conversion: {report.weakest.label} "
            f"{report.weakest.rate}% n={report.weakest.n}"
        )
    console.print(report.suggested_experiment)
    console.print("Differences are percentage points. No causal claim.")


@app.command("experiments")
def experiments_command() -> None:
    """List local prospecting experiments."""
    from leadfinder.application.service import LeadService

    service = LeadService()
    rows = service.experiments()
    if not rows:
        console.print("No experiments yet. Create one from Insights in the GUI.")
        return
    table = Table(title="Experiments", show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Target")
    for item in rows:
        from leadfinder.experiments import target_label

        table.add_row(str(item.id), item.name, item.status, target_label(item))
    console.print(table)


experiment_app = typer.Typer(help="Inspect a single experiment.")
app.add_typer(experiment_app, name="experiment")


@experiment_app.command("show")
def experiment_show_command(experiment_id: int) -> None:
    """Show one experiment vs the current baseline. No network."""
    from leadfinder.analytics import format_rate
    from leadfinder.application.service import LeadService

    service = LeadService()
    experiment = service.get_experiment(experiment_id)
    if experiment is None:
        err_console.print("[red]Experiment not found.[/red]")
        raise typer.Exit(code=1)
    metrics = service.experiment_metrics(experiment, days=0)
    console.print(f"{experiment.name} [{experiment.status}]")
    console.print(experiment.hypothesis or "(no hypothesis)")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Target", metrics.target_label)
    table.add_row("Baseline", format_rate(metrics.baseline))
    table.add_row("Observed", format_rate(metrics.observed))
    table.add_row("Sample", str(metrics.sample))
    table.add_row(
        "Difference",
        "n/a" if metrics.difference_pp is None else f"{metrics.difference_pp} pp",
    )
    table.add_row("Evaluation", metrics.evaluation)
    console.print(table)
    console.print("Descriptive comparison only. No causal claim.")


@app.command("campaigns")
def campaigns_command() -> None:
    """List local campaigns."""
    from leadfinder.application.service import LeadService

    service = LeadService()
    rows = service.campaigns()
    if not rows:
        console.print("No campaigns yet. Run a search or create one in the GUI.")
        return
    table = Table(title="Campaigns", show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Location")
    table.add_column("Preset")
    for item in rows:
        table.add_row(str(item.id), item.name, item.location, item.business_preset)
    console.print(table)


@app.command("backup")
def backup_command(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination .db file."),
    ] = None,
) -> None:
    """Copy the local SQLite workspace with the SQLite backup API."""
    from leadfinder.application.service import LeadService
    from leadfinder.paths import backup_filename, data_dir

    try:
        destination = output or data_dir() / backup_filename()
        written = LeadService().backup(destination)
        console.print(f"Backup saved to {written}")
    except LeadFinderError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


@app.command("restore")
def restore_command(
    path: Annotated[Path, typer.Argument(help="LeadFinder SQLite backup (.db).")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Skip confirmation. Still writes a safety backup first."),
    ] = False,
) -> None:
    """Replace the local database from a backup after saving a safety copy."""
    from leadfinder.application.service import LeadService

    if not yes:
        confirmed = typer.confirm(
            "This replaces the current local database after saving a safety backup. Continue?"
        )
        if not confirmed:
            raise typer.Abort()
    try:
        safety = LeadService().restore(path)
        console.print(f"Restore complete. Previous database saved to {safety}")
    except LeadFinderError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


@app.command("templates")
def templates_command() -> None:
    """List local pitch templates. No network."""
    from leadfinder.application.service import LeadService

    rows = LeadService().list_templates()
    if not rows:
        console.print("No pitch templates yet. Create them in the GUI Sales Prep tab.")
        return
    table = Table(title="Pitch templates", show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Updated")
    for item in rows:
        table.add_row(str(item.id), item.name, item.updated_at)
    console.print(table)


@app.command("costs")
def costs_command() -> None:
    """Show the local Places pricing catalog and campaign estimates. No network."""
    from leadfinder.application.service import LeadService
    from leadfinder.costs.aggregation import format_campaign_costs, summarize_campaign_costs
    from leadfinder.costs.pricing import default_catalog

    catalog = default_catalog()
    console.print(
        f"Pricing catalog {catalog.version} ({catalog.currency}, "
        f"reference {catalog.reference_date}, verified {catalog.verified_at})"
    )
    console.print(catalog.source)
    for sku, rate in catalog.rates_per_thousand.items():
        label = catalog.sku_labels.get(sku, sku)
        console.print(f"  {label}: {catalog.currency} {rate} list per 1,000")
    service = LeadService()
    report = service.analytics_report(service.analytics_period(days=None))
    console.print(
        format_campaign_costs(
            summarize_campaign_costs(
                service.store.list_searches(limit=0),
                campaign_id=0,
                discovered_leads=report.historical.total_leads,
                high_opportunity_leads=report.snapshot.high_opportunity,
                interested_once=report.historical.interested_once,
                won_once=report.historical.won_once,
            )
        )
    )


@app.command("demo-data")
def demo_data_command(
    db: Annotated[Path, typer.Option("--db", help="SQLite path. Refuses the default user DB.")],
) -> None:
    """Write a synthetic demo database. Refuses the default user DB."""
    from leadfinder.demo import seed_demo_database

    try:
        written = seed_demo_database(db)
    except LeadFinderError as error:
        err_console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    console.print(f"Demo database written to {written}")


@app.command("doctor")
def doctor_command() -> None:
    """Check local database, schema, and configuration. Never prints keys."""
    from leadfinder.doctor import format_doctor, run_doctor

    report = run_doctor()
    console.print(format_doctor(report))
    if not report.ok():
        raise typer.Exit(code=1)


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
