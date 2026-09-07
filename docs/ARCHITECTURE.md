# Architecture

LeadFinder 1.1 is a local-first Python package (`leadfinder`) with a Typer CLI and an optional PySide6 GUI. Both use the same application service. This is not a strict clean-architecture rewrite: GUI still coordinates workers and pages; storage is a facade over domain mixins.

```text
CLI / GUI
    ↓
Application (LeadService facade)
    ↓
Domain
 ├ Discovery      (Places client, search, normalize, filter)
 ├ Qualification  (scoring, digital presence, duplicate hints)
 ├ Workflow       (status, follow-ups, activities, campaigns, priority)
 ├ Analytics      (snapshot + historical rates)
 ├ Insights       (deterministic segment ranking)
 ├ Experiments    (descriptive vs baseline)
 └ AI             (optional Groq: sales prep, aggregated explanations)
    ↓
Storage / external adapters
 ├ SQLite (LocalLeadStore facade + mixins)
 ├ Places HTTP
 └ Groq HTTP
```

## Dependency boundaries

- **GUI / CLI** collect input and format output. They must not contain Places HTTP, Groq prompts, or SQL.
- **Application (`LeadService`)** is the public facade used by GUI and CLI. Internals still live in domain modules; the facade was kept so callers do not import repositories.
- **Domain** owns scoring, workflow rules, analytics semantics, insights, experiments, and duplicate detection.
- **Storage** owns parameterized SQL, migrations, backup/restore, and workspace merge. `LocalLeadStore` composes connection, leads, activities, campaigns, experiments, and workspace mixins.
- **External adapters** (`places_client`, `ai/groq_provider`, `digital_presence`) talk to the network. GUI workers call the service, never widgets from worker threads.

Direction of dependencies: GUI/CLI → Application → Domain → Storage / adapters. Analytics/insights/experiments do not import Qt. Storage does not import GUI.

## GUI composition

`main_window.py` is the root coordinator (workers, tabs, file menu, wiring). Widget construction lives in:

- `search_panel.py` — search form, cost preview, progress, summary
- `filter_bar.py` — session filters and named saved filters
- `lead_details.py` — overview, workflow, sales prep tab

Named filters are QSettings JSON (filter config only, not result sets). Manual priority is SQLite (`manual_priority`), distinct from automatic opportunity score.

## Schema

Incremental migrations in `storage/schema.py`. Current version is **7** (`manual_priority` on `leads_local`). Opening a store always migrates forward. Historical versions 1–6 remain supported.

SQLite uses WAL and `busy_timeout=5000`. Backup uses the sqlite3 backup API (copies the live WAL-backed database). Restore validates, writes a safety copy, then replaces the file; a failed restore reopens the safety copy.

## Insights and experiments

Insights rank segments against `contact_to_interest` using percentage-point differences. Combinations use at most two dimensions. Unknown and tiny samples are omitted. Experiments compare a scoped observed rate to the period baseline and label Insufficient data / Above / Near / Below — never Success/Failure from small n. Won still counts historically as contacted/interested when status or events imply it; snapshot current status is separate.

## AI

`AIProvider` implements sales prep. Insights explanations are a second Groq JSON call with aggregated payloads (`analytics_insights_v1` / `experiment_summary_v1`). Providers must not send outreach. Groq env (`GROQ_API_KEY`, `GROQ_MODEL`) is read through `config.py`, same as Places keys.

## Paths

Data and logs use `platformdirs` (`LeadFinder` / `LeadFinder`). No hardcoded home directories. Unexpected errors log a traceback via the rotating redacting logger; GUI shows a generic message.
