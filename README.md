# Local Business Lead Finder

Cost-aware Python CLI and desktop app for discovering, qualifying, preparing, and measuring local business leads with Google Places API (New).

[![CI](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml)

Independent project. **Not affiliated with Google.** Version **1.2.0**.

**Stack:** Python 3.10+ · Google Places API (New) · Typer · Rich · PySide6 · SQLite · optional Groq · pytest · Ruff · mypy · GitHub Actions

```text
Discover → Qualify → Track → Analyze → Learn
Prepare → Decide → Act → Recover → Measure cost
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

**Desktop workflow** — pipeline, follow-ups, activity history, campaigns, manual priority, saved filters, conservative duplicate hints (in-session phone/domain plus historical name+locality), manual undo, pitch templates, lead compare. Outreach is always manual.

**Cost** — local estimated Places Text Search **list-price** (not an invoice). Search planner compares 1/2/3 pages with no network. Campaign analytics show estimated list cost per discovered / high-opportunity lead when data exists.

**Analytics** — snapshot (today) vs historical conversions. Insights rank segments vs baseline in **percentage points**. Experiments store a hypothesis and compare observed rate vs baseline without declaring scientific success/failure.

**AI (optional)** — Groq Sales Prep for one selected lead after **Generate**. Optional selected pitch template is stylistic guidance only. Insights/experiment explanations send **aggregates only**.

**Local data** — SQLite under the OS app-data directory (`platformdirs`). Backup / restore / workspace ZIP (format 1: templates + non-sensitive saved filters) / `leadfinder doctor`. `leadfinder demo-data --db PATH` seeds a disposable synthetic DB (refuses the default user file).

## Screenshots

Add real captures when you have them (do not commit fabricated images):

```text
docs/images/search.png
docs/images/pipeline.png
docs/images/analytics.png
docs/images/insights.png
docs/images/costs.png
```

No fabricated UI images are in the repo. Capture the real GUI at 1366×768; see [docs/images/README.md](docs/images/README.md).

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

Default field profile is `enterprise` because `websiteUri` is required to find missing websites. `websiteUri`, phone, and rating bill **Text Search Enterprise** (list $35 / 1,000 in the first PAYG band), not Pro.

LeadFinder estimates Google Places **list-price** usage from completed page requests and the field mask SKU. It does not read Google Cloud Billing and cannot know actual invoiced cost (free usage, subscriptions, credits, other projects, retries, taxes).

You are responsible for Places API billing, attribution, and contact rules.

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

## After 1.1

Keep the product local-first. Do not add outreach automation.

## License

MIT. See `LICENSE`.
