# Architecture

LeadFinder 1.2 is a local-first Python package (`leadfinder`) with a Typer CLI and an optional PySide6 GUI. Both use the same application service. This is not a strict clean-architecture rewrite: GUI still coordinates workers and pages; storage is a facade over domain mixins.

```text
CLI / GUI
    ↓
Application (LeadService facade)
    ↓
Domain
 ├ Discovery      (Places client, search, normalize, filter)
 ├ Qualification  (scoring, digital presence, duplicate hints)
 ├ Workflow       (status, follow-ups, activities, campaigns, priority, undo)
 ├ Templates      (manual pitch text, explicit placeholders)
 ├ Costs          (usage accounting, pricing catalog, estimates)
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

## Workflow undo

Pure rules live in `undo.py` (`can_undo`, `latest_undoable`). Eligible types: `status_change`, `follow_up`, `priority_change`. Undo never deletes rows; it applies the previous value and inserts an inverse activity (`reason: undo`, `reverses_activity_id`). Stale if a later undoable event exists, the original was already reversed, or current state ≠ original `new_value`. GUI: details Undo + status-bar button.

## Pitch templates

User-created SQLite rows (`pitch_templates`). `templates.render_template` substitutes known `{placeholders}` only; unknown tokens and empty values stay visible. No `eval`. Workspace ZIP includes `pitch_templates.json`. Groq may receive truncated `selected_template` as style guidance; it does not send phone, website, or place_id.

## Cost estimation

`costs/` separates pricing catalog, SKU classification, list-price estimates, and campaign aggregation. Widgets must not hardcode rates.

**Product field profiles** (`essentials` / `pro` / `enterprise`) are convenience masks. **Billing SKUs** are computed from the actual field mask (`billing_sku_for_field_mask`):

- IDs only → Text Search Essentials (IDs Only), list $0 / 1,000
- `displayName` and other Pro fields → Text Search Pro, list $32 / 1,000
- `websiteUri`, `rating`, `userRatingCount`, phone → Text Search Enterprise, list $35 / 1,000
- `reviews` and other Atmosphere fields → Text Search Enterprise + Atmosphere, list $40 / 1,000

The highest SKU required by any requested field wins. Catalog `google_places_text_search_new_2026_08` (USD first PAYG band; `reference_date` 2025-03-01, `verified_at` 2026-09-06) is a list-price model, not “effective forever.” LeadFinder does not read Google Cloud Billing and does not subtract monthly free usage, subscriptions, credits, volume discounts, taxes, or other projects.

Cost math uses **completed page requests** (`api_requests` / logical Text Search calls). `http_attempts` counts retry POSTs separately and is **not** used in the list-price estimate. Old `search_runs` without request count / SKU / profile show Unknown. No fictitious backfill.

Currency is catalog USD. No FX. Analytics never labels CAC/ROI/profit.

## Duplicate hints (compliance)

SQLite still does **not** persist phones or websites. Historical scan uses `label` + `source_location` maps (not O(n²) fuzzy). Phone and website domain compare only among in-memory session leads. Generic short names are skipped. Records are never merged.

## Dependency boundaries

- **GUI / CLI** collect input and format output. They must not contain Places HTTP, Groq prompts, or SQL.
- **Application (`LeadService`)** is the public facade used by GUI and CLI. Internals still live in domain modules; the facade was kept so callers do not import repositories.
- **Domain** owns scoring, workflow rules, analytics semantics, insights, experiments, and duplicate detection.
- **Storage** owns parameterized SQL, migrations, backup/restore, and workspace merge. `LocalLeadStore` composes connection, leads, activities, campaigns, experiments, templates, and workspace mixins.
- **External adapters** (`places_client`, `ai/groq_provider`, `digital_presence`) talk to the network. GUI workers call the service, never widgets from worker threads.

Direction of dependencies: GUI/CLI → Application → Domain → Storage / adapters. Analytics/insights/experiments do not import Qt. Storage does not import GUI.

## GUI composition

`main_window.py` is the root coordinator (workers, tabs, file menu, wiring). Widget construction lives in:

- `search_panel.py` — search form, cost preview / page planner, progress, summary
- `filter_bar.py` — session filters, named saved filters, compare selected
- `lead_details.py` — overview, workflow, undo, sales prep tab
- `pitch_panel.py` — template picker inside Sales Prep
- `compare_dialog.py` — 2–5 lead comparison table

Named filters are QSettings JSON (filter config only, not result sets) and are also exported in workspace `settings-non-sensitive.json`. Manual priority is SQLite (`manual_priority`), distinct from automatic opportunity score.

## Schema

Incremental migrations in `storage/schema.py`. Current version is **9** (`search_runs.billing_sku`, plus v8 undo/cost/template columns). Opening a store always migrates forward. Historical versions 1–8 remain supported. Workspace ZIP format stays **1** with optional `pitch_templates.json` and saved filters.

SQLite uses WAL and `busy_timeout=5000`. Backup uses the sqlite3 backup API (copies the live WAL-backed database). Restore validates, writes a safety copy, then replaces the file; a failed restore reopens the safety copy.

## Insights and experiments

Insights rank segments against `contact_to_interest` using percentage-point differences. Combinations use at most two dimensions. Unknown and tiny samples are omitted. Experiments compare a scoped observed rate to the period baseline and label Insufficient data / Above / Near / Below — never Success/Failure from small n. Won still counts historically as contacted/interested when status or events imply it; snapshot current status is separate.

## AI

`AIProvider` implements sales prep. Insights explanations are a second Groq JSON call with aggregated payloads (`analytics_insights_v1` / `experiment_summary_v1`). Providers must not send outreach. Groq env (`GROQ_API_KEY`, `GROQ_MODEL`) is read through `config.py`, same as Places keys.

## Paths

Data and logs use `platformdirs` (`LeadFinder` / `LeadFinder`). No hardcoded home directories. Unexpected errors log a traceback via the rotating redacting logger; GUI shows a generic message.
