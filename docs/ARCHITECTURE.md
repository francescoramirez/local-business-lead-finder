# Architecture

LeadFinder 1.0 is a local-first Python package (`leadfinder`) with a Typer CLI and an optional PySide6 GUI. Both use the same application service.

```text
CLI / GUI
    ↓
Application Service
    ↓
Core
 ├ Discovery      (Places client, search, normalize, filter)
 ├ Qualification  (scoring, digital presence)
 ├ Workflow       (status, follow-ups, activities, campaigns)
 ├ Analytics      (snapshot + historical rates)
 ├ Insights       (deterministic segment ranking)
 └ AI             (optional Groq: sales prep, aggregated explanations)
    ↓
SQLite / External APIs
```

## Boundaries

- **CLI / GUI** format results and collect input. They do not embed prompts, SQL, or Places HTTP.
- **LeadService** is the facade for search, workflow, analytics, insights, experiments, backup/restore, and workspace ZIP.
- **SQLite** (`LocalLeadStore`) holds user-generated metadata only: Place IDs, labels, statuses, notes, tags, follow-ups, activities, campaigns, search-run summaries, experiments.
- **Not stored:** Google Places JSON, phone numbers, websites, HTML, API keys, transient AI generations (unless the user saves prep into notes).
- **External APIs** run only when the user searches, analyzes a URL, or clicks Generate / Explain.

## Schema

Incremental migrations in `storage/schema.py`. Current version is **6** (experiments). Opening a store always migrates forward.

## Insights and experiments

Insights rank segments against `contact_to_interest` using percentage-point differences. Combinations use at most two dimensions. Unknown and tiny samples are omitted. Experiments compare a scoped observed rate to the period baseline and label Insufficient data / Above / Near / Below — never Success/Failure from small n.

## AI

`AIProvider` implements sales prep. Insights explanations are a second Groq JSON call with aggregated payloads (`analytics_insights_v1` / `experiment_summary_v1`). Providers must not send outreach.

## Paths

Data and logs use `platformdirs` (`LeadFinder` / `LeadFinder`). No hardcoded home directories.
