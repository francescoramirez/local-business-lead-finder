# Local Business Lead Finder

Desktop prospecting workflow for local businesses.

```text
Discover → Qualify → Track → Learn
```

[![CI](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml)

Independent project. **Not affiliated with Google.** Version **1.3.0**.

LeadFinder is a **local-first** desktop app (and CLI) for discovering, qualifying, preparing, and measuring local business leads with Google Places API (New). Outreach is always **manual**. Your workflow data stays on this computer.

**Stack:** Python 3.10+ · PySide6 · SQLite · Typer · Rich · optional Groq · pytest · Ruff · mypy · PyInstaller (Windows x64)

## Try Demo Mode

Open LeadFinder and choose **Try Demo**. You get synthetic businesses, pipeline, analytics, pitch templates, and estimated list-cost examples. Demo Mode does **not** call Google or Groq and does **not** write your real workspace database.

## Windows desktop

Packaged Windows x64 builds use **Python 3.12 x64** as the official packager (`.\packaging\build_windows.ps1`). Source still runs on Python 3.10+.

See [docs/DESKTOP_BUILD.md](docs/DESKTOP_BUILD.md) and [docs/CLEAN_WINDOWS_TEST.md](docs/CLEAN_WINDOWS_TEST.md). The owner publishes installer and ZIP assets on a **GitHub Release** when ready. There is no download URL in this README until that release exists.

The installed app does **not** require Python, Git, or VS Code. User data stays in the OS app-data folder and survives uninstall. Builds are unsigned; Windows SmartScreen may warn.

## Python / development

```bash
python -m pip install -e ".[gui]"
leadfinder gui
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

## Core workflow

```text
Discover → Qualify → Prioritize → Contact manually → Track → Measure → Learn
```

Desktop tabs: **Search**, **Pipeline**, **Prospects**, **Dashboard**, **Learn** (Analytics / Insights / Experiments).

## Features

**Discovery** — Google Places API (New), cost-aware field masks, dry-run, pagination, retries.

**Qualification** — deterministic lead scoring and optional digital-presence checks (no crawl, no JavaScript).

**Desktop workflow** — first-run onboarding, Demo Mode, Settings/About, pipeline, follow-ups, activity history, campaigns, manual priority, saved filters, conservative duplicate hints, manual undo, pitch templates, lead compare.

**Cost** — local estimated Places Text Search **list-price** (not an invoice). Search planner compares 1/2/3 pages with no network.

**Analytics** — snapshot vs historical conversions. Insights rank segments vs baseline in **percentage points**.

**AI (optional)** — Groq Sales Prep for one selected lead after **Generate**. Insights explanations send **aggregates only**.

**Local data** — SQLite under the OS app-data directory (`platformdirs`). Backup / restore / workspace ZIP / `leadfinder doctor`.

## Screenshots

Add real captures when you have them (do not commit fabricated images):

```text
docs/images/search.png
docs/images/pipeline.png
docs/images/analytics.png
docs/images/insights.png
docs/images/costs.png
```

Capture the real GUI at 1366×768 from **Demo Mode**; see [docs/images/README.md](docs/images/README.md).

## Architecture

```text
CLI / GUI
    ↓
Application Service
    ↓
Core
    ↓
SQLite / Places / optional Groq
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DESKTOP_BUILD.md](docs/DESKTOP_BUILD.md).

## Privacy

No cloud account. No telemetry. No auto outreach.

SQLite stores user workflow metadata (status, notes, tags, follow-ups, activities, campaigns, experiments). It does **not** cache Google Places payloads, phone numbers, websites, or HTML.

API keys come from the **environment** or the **OS credential store** (Windows Credential Manager via `keyring` when available). They are never stored in SQLite, QSettings, logs, or workspace ZIP files.

LeadFinder estimates Google Places list-price usage. It does not read Google Cloud Billing and cannot know actual invoiced cost.

## Google Places

Default field profile is `enterprise` because `websiteUri` is required to find missing websites. See the architecture doc for SKU mapping.

```env
GOOGLE_MAPS_API_KEY=your-places-api-key-here
# optional alias
# GOOGLE_PLACES_API_KEY=your-places-api-key-here
# optional AI
# GROQ_API_KEY=your-groq-api-key-here
```

Keys are never CLI flags. In the desktop app, Settings → API can save keys to the OS store.

You are responsible for Places API billing, attribution, and contact rules.

## Testing

```bash
python -m pip install -e ".[dev,gui]"
pytest
ruff check .
mypy src/leadfinder
```

GUI tests use `QT_QPA_PLATFORM=offscreen`. Tests mock Google, Groq, and website HTTP. No real network.

## CLI

```bash
leadfinder presets
leadfinder dry-run --business cafe --location "Mar del Plata" --region "Buenos Aires" --country AR
leadfinder analytics
leadfinder insights
leadfinder campaigns
leadfinder experiments
leadfinder stats
leadfinder costs
leadfinder templates
leadfinder doctor
leadfinder diagnostics
leadfinder demo-data --help
leadfinder gui
```

## License

MIT. See `LICENSE`.
