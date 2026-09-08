# Changelog

All notable LeadFinder versions. Dates are omitted when they cannot be derived from the repository.

## 1.3.0

### Added

- Windows x64 desktop packaging: PyInstaller one-folder app, optional Inno Setup per-user installer, standalone ZIP, release manifest and SHA-256 sums.
- First-run onboarding (Welcome → How it works → Google Places → Demo) stored in QSettings, with Help → Show Welcome.
- Isolated Demo Mode (`leadfinder-demo.db`) with reset and return to My Workspace. Synthetic data only; no Google/Groq.
- Settings, About, copy-diagnostics, Open data folder, and a Places list-price notice before the first real search.
- Optional OS credential storage (`keyring`) for Places and Groq keys, with environment variables still taking precedence.
- Official Windows packager is Python 3.12 x64 (source remains 3.10+). Isolated venv, `%TEMP%` PyInstaller staging, packaged QA hooks, `tzdata` for IANA zones, and `docs/CLEAN_WINDOWS_TEST.md`.

### Changed

- Startup uses a frozen-resource helper, user-data paths stay in `platformdirs`, and GUI errors avoid raw tracebacks.
- README, architecture, security, and new desktop/release docs describe packaging, unsigned-build SmartScreen, and list-price cost semantics.

### Fixed

- Developer `.env` is no longer loaded from the packaged install directory, so keys are not expected next to `LeadFinder.exe`.
- Demo Pipeline loads persisted leads from the active workspace store instead of empty Search-session memory, so Demo Mode shows the seeded workflow board (New / Contacted / Interested / Follow-up / Won).

## 1.2.0

### Added

- Safe workflow undo for the latest status, follow-up, or manual priority change. History is never deleted; undo writes an inverse activity.
- Historical duplicate hints using allowed local metadata (normalized name + locality). Phone/website remain session-only.
- Saved filters travel in workspace ZIP (`settings-non-sensitive.json`) with merge names such as `Best prospects (Imported)`.
- Manual pitch templates in SQLite, `{placeholder}` rendering (missing tokens stay visible), GUI picker, optional Groq style context.
- Local Places **list-price** estimates (Decimal, USD catalog `google_places_text_search_new_2026_08`) on dry-run, search summary, and campaign analytics. SKU is derived from the field mask, not from the product profile name.
- Search planner: 1/2/3 page request/cost preview with no network.
- Compare 2–5 selected leads. Context menu quick actions (contacted, follow-up, priority high, copy phone, open website, copy pitch).
- `leadfinder demo-data --db`, `templates`, and `costs` CLI helpers.

### Changed

- Schema v8–v9: activity undo metadata, search-run cost fields and `billing_sku`, `pitch_templates`. Workspace format stays **1** with optional files.
- Dry-run CLI/GUI output includes estimated list cost. Doctor reports pricing catalog version, reference date, and verified-at. Field-mask SKU mapping: IDs-only $0 list / Pro $32 / Enterprise $35 / Enterprise+Atmosphere $40 per 1,000 (first PAYG band). Monthly free usage is not subtracted.

### Fixed

- Incorrect Places list-price mapping that treated product field-profile names as SKUs (essentials/pro/enterprise as $32/$35/$40). Costs now use mask-derived SKUs.
- Duplicate hint text now states the matching reason (phone, domain, or name+locality) instead of a single generic line.

## 1.1.0

### Added

- Local manual priority (High / Normal / Low / Ignore), stored in SQLite and distinct from automatic opportunity score.
- Named saved filters (configuration only, including built-in presets) in desktop settings.
- Conservative in-session “Possible duplicate” hints (same phone, same website domain, or same normalized name plus locality). Records are never merged automatically.

### Changed

- Storage is a `LocalLeadStore` facade over connection, leads, activities, campaigns, experiments, and workspace mixins. Schema v7.
- Desktop search, filters, and lead details are composed from dedicated widgets; `MainWindow` remains the coordinator.
- Groq and Places environment keys are read through `config.py`. Shared presence/opportunity labels live in `labels.py`.
- Worker unexpected errors log a traceback; restore fallback logs if the safety database cannot be reopened.
- Workspace merge runs in a single transaction. SQLite connections set `busy_timeout`. Groq empty responses map to validation errors (no retry).

### Fixed

- HTML parser failures in digital presence log a warning instead of failing silently.
- Table header restore no longer swallows every exception type.

## 1.0.0

Product hardening for a 1.0 release candidate: UX grouping under Learn, empty states, backup filename stamps, doctor, restore, workspace ZIP, docs (README, CONTRIBUTING, SECURITY, ARCHITECTURE), CLI `--verbose` / `--version`, package metadata, synthetic E2E and query-budget tests. No large new product features.

## 0.9.0

Local data portability and recovery: SQLite backup API with timestamped files, safe restore (validate, safety copy, confirm), workspace ZIP export/import (merge by Place ID), `leadfinder doctor`, friendlier corrupt-DB errors. Workspace replace-by-file is restore; full CRM-style merge remains limited.

## 0.8.0

Local experiments: draft/active/completed/archived, hypothesis text, create-from-insight (no auto-search), campaign association, descriptive evaluation vs baseline (Insufficient data / Above / Near / Below). Schema v6.

## 0.7.0

Outcome-driven insights on historical analytics: baseline vs segments, percentage-point uplift, sample thresholds, Low/Medium/High confidence from n, two-dimension combinations, Insights GUI + `leadfinder insights`, optional aggregated AI explanation (`analytics_insights_v1`).

## 0.6.0

Campaign analytics: snapshot vs event-based history, campaigns, Analytics tab, `leadfinder analytics` / `campaigns`.

## 0.5.0

Optional Groq AI Sales Prep. User-triggered, one selected lead, structured JSON, no outreach.

## 0.4.0

Commercial workflow: pipeline, follow-ups, activity history, dashboard, SQLite migrations.

## 0.3.0

Digital presence qualification and opportunity scoring.

## 0.2.0

Deterministic lead scoring, desktop GUI, local SQLite metadata.

## 0.1.0

CLI search over Google Places API (New): presets, dry-run, export CSV/JSON.
