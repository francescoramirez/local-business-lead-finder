# Local Business Lead Finder

Cost-aware Python CLI and desktop app for discovering, qualifying, preparing, and measuring local business leads with Google Places API (New).

[![CI](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml)

Independent project. **Not affiliated with Google.** Version **1.0.0**.

**Stack:** Python 3.10+ · Google Places API (New) · Typer · Rich · PySide6 · SQLite · optional Groq · pytest · Ruff · mypy · GitHub Actions

```text
Discover → Qualify → Track → Analyze → Improve
```

Local-first, single-user, privacy-conscious, explainable, **manual outreach**. Not a cloud CRM, spam engine, or predictive ML system.

## Quick start

```bash
python -m pip install -e .
leadfinder --help
leadfinder --version
```

Plan a search without spending API credits (no key, no network):

```bash
leadfinder dry-run \
  --business cafe \
  --location "Mar del Plata" \
  --region "Buenos Aires" \
  --country AR
```

```bash
python -m pip install -e ".[gui]"
leadfinder gui
```

## Core workflow

```text
Discover → Qualify → Prioritize → Prepare → Contact manually → Track → Measure → Learn → Plan next campaign
```

Desktop tabs: **Search**, **Pipeline**, **Prospects**, **Dashboard**, **Learn** (Analytics / Insights / Experiments).

## Features

**Discovery** — Google Places API (New), cost-aware field masks, dry-run, pagination, retries.

**Qualification** — deterministic lead scoring and optional digital-presence checks (no crawl, no JavaScript).

**Desktop workflow** — pipeline, follow-ups, activity history, campaigns. Outreach is always manual.

**Analytics** — snapshot (today) vs historical conversions. Insights rank segments vs baseline in **percentage points**. Experiments store a hypothesis and compare observed rate vs baseline without declaring scientific success/failure.

**AI (optional)** — Groq Sales Prep for one selected lead after **Generate**. Insights/experiment explanations send **aggregates only**.

**Local data** — SQLite under the OS app-data directory (`platformdirs`). Backup / restore / workspace ZIP / `leadfinder doctor`.

## Screenshots

Add real captures when you have them (do not commit fabricated images):

```text
docs/images/search.png
docs/images/pipeline.png
docs/images/analytics.png
docs/images/insights.png
```

## Architecture

```text
CLI / GUI
    ↓
Application Service
    ↓
Core
 ├ Discovery
 ├ Qualification
 ├ Workflow
 ├ Analytics
 ├ Insights
 └ AI (optional)
    ↓
SQLite / External APIs (Places, Groq)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Privacy

SQLite stores user workflow metadata (status, notes, tags, follow-ups, activities, campaigns, experiments). It does **not** cache Google Places payloads, phone numbers, websites, or HTML. API keys are environment-only and are never logged or persisted.

## AI

Optional. Discovery, scoring, and tracking work with no Groq key. Sales Prep is user-triggered for one lead. Analytics explanations never receive individual leads.

## Google Places

Default field profile is `enterprise` because `websiteUri` is required to find missing websites. You are responsible for Places API billing, attribution, and contact rules.

```env
GOOGLE_MAPS_API_KEY=your-places-api-key-here
# optional alias
# GOOGLE_PLACES_API_KEY=your-places-api-key-here
# optional AI
# GROQ_API_KEY=your-groq-api-key-here
# GROQ_MODEL=llama-3.3-70b-versatile
```

Keys are never CLI flags.

## Testing

```bash
python -m pip install -e ".[dev,gui]"
pytest
ruff check .
mypy src/leadfinder
```

GUI tests use `QT_QPA_PLATFORM=offscreen`. Tests mock Google, Groq, and website HTTP. No real network.

Run `pytest` locally for the current count. CI runs Ruff, pytest, and mypy without secrets.

## CLI

```bash
leadfinder --verbose
leadfinder presets
leadfinder search --help
leadfinder analytics --days 90
leadfinder insights --days 90
leadfinder campaigns
leadfinder experiments
leadfinder experiment show 1
leadfinder stats
leadfinder backup
leadfinder restore path.db --yes
leadfinder doctor
leadfinder gui
```

## After 1.0

Keep the product local-first. Likely next: real GUI screenshots, optional workspace merge refinements, and more campaign notes. No outreach automation.

## License

MIT. See `LICENSE`.
