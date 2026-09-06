# Local Business Lead Finder

Cost-aware Python CLI and desktop app for discovering and prioritizing local business leads using Google Places API.

[![CI](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/francescoramirez/local-business-lead-finder/actions/workflows/ci.yml)

Turn a business type and a location into a ranked outreach list: Google Places API (New) → normalize → filter → score → digital presence → optional AI sales prep → CSV/JSON. Built for web agencies looking for local businesses with weak or missing websites.

Independent project. **Not affiliated with Google.**

**Stack:** Python 3.10+ · Google Places API (New) · Typer · Rich · PySide6 · pytest · Ruff · mypy · GitHub Actions

## Quick start

```bash
python -m pip install -e .
leadfinder --help
```

Plan a search without spending API credits (no key, no network):

```bash
leadfinder dry-run \
  --business cafe \
  --location "Mar del Plata" \
  --region "Buenos Aires" \
  --country AR
```

Example / synthetic dry-run output:

```text
Dry run
  Business preset     cafe
  Search terms        cafe
  Locations           1
  Country             AR
  Region              Buenos Aires
  Max queries         1
  Max API requests    1
  Page size           20
  Pages               1
  Field profile       enterprise
  Billing tier        Text Search Enterprise
  Locations:
    - Mar del Plata

No API requests were made.
```

Then run a real search (requires `GOOGLE_MAPS_API_KEY`):

```bash
leadfinder search \
  --business cafe \
  --location "Mar del Plata" \
  --region "Buenos Aires" \
  --country AR
```

```bash
leadfinder presets
```

## Desktop GUI

The same search engine is available as a small CRM-style desktop app: configure a search, qualify digital presence, prepare a draft pitch for one selected prospect, track follow-ups, and export.

```text
Discover → Qualify → Select prospect → AI Sales Prep → Review → Manual contact → Track outcome
```

```bash
python -m pip install -e ".[gui]"
leadfinder gui
```

`pip install -e .` still installs the CLI only. If you run `leadfinder gui` without the extra, the app tells you how to install PySide6.

Screenshot paths (add real captures when you have them):

```text
docs/images/leadfinder-gui.png
docs/images/leadfinder-dashboard.png
docs/images/leadfinder-pipeline.png
```

Local contact status, notes, tags, follow-ups, and activity history are stored in SQLite under the OS application-data directory. Google Places payloads, phone numbers, websites, and HTML are not cached there. A short local label (the displayed business name from a search you ran) is kept only so the Prospects list stays readable.

## Prospect workflow

Statuses: New → Contacted → Interested → Follow-up → Won, plus exits Rejected and Do not contact. Transitions are manual.

Each prospect can have a next follow-up (UTC in storage, local time in the GUI). Overdue means the follow-up time has passed and the status is not Won / Rejected / Do not contact.

Activity history is recorded locally when you change status, schedule a follow-up, add a contact attempt, or save AI sales prep into notes. Nothing is sent automatically — no email, WhatsApp, or DMs.

The GUI has Search, Pipeline, Prospects, and Dashboard tabs. Lead details include Overview and Sales Prep. Dashboard shows pipeline counts, a simple funnel, and recent search metadata (preset, location, lead counts) without storing Places results.

```bash
leadfinder stats
leadfinder backup --output leadfinder-backup.db
```

## Digital presence qualification

LeadFinder can classify obvious digital-presence signals such as:

- no website
- social profile used as website
- link-in-bio page
- unreachable domain
- HTTP-only site
- obvious parked/placeholder page
- extremely thin pages, only when several signals agree

This is **not** a security scanner or a full website-quality audit. It does not crawl sites, run JavaScript, fingerprint browsers, or scrape emails. Website analysis is optional and off by default (`--analyze-websites` or the GUI checkbox / **Analyze websites** button).

```bash
leadfinder analyze https://instagram.com/example
leadfinder search --business cafe --location "Mar del Plata" --country AR --analyze-websites
```

Each lead gets a **lead score** (existing commercial signals) and an **opportunity score** (commercial + digital-opportunity points) with a High / Medium / Low label.

## AI-assisted sales prep

Optional. Discovery, scoring, and pipeline tracking work with no AI key.

When you explicitly select one prospect and click **Generate sales prep**, LeadFinder sends a small set of already-visible commercial signals to the configured provider (Groq) and returns a structured draft for you to review. It does not send messages, open WhatsApp, mail anyone, change pipeline status, or run against the whole list.

```text
AI sales prep is not configured.

Set GROQ_API_KEY to enable it.
```

```env
GROQ_API_KEY=your-groq-api-key-here
# optional
GROQ_MODEL=llama-3.3-70b-versatile
```

The key is read from the environment / `.env` only. It is not a CLI flag, not shown in Settings, and not stored in SQLite or QSettings. Model name and output language (Spanish by default, or English) may be saved locally.

**Sent (selected lead only, after Generate):** business name, type, general location/region/country, rating, review count, digital-presence category, qualification signals, opportunity score/level, contact status, notes, tags, website-status code, operational flag, requested language.

**Not sent:** API keys, phone numbers, Place IDs, websites/URLs, Google payloads, HTML, other leads, logs.

The model sees structured signals, not a site scrape. Output is JSON (`sales_prep_v1`): opportunity summary, pitch angle, value props, suggested opener (a draft), talking points, objections, cautions, next step, observed vs suggestion, information gaps.

Example (synthetic):

```text
Observed
• Social-only presence
• 238 reviews
• Operational

Opportunity summary
Strong local activity with 238 reviews, but Instagram appears to be the primary web presence.

Suggested angle
Position a standalone site as a complement to Instagram, focused on menu visibility and direct inquiries.

Suggested draft
Hola, vi que tienen una presencia bastante activa en Instagram...

Cautions
• Do not frame their current presence as bad
• Do not promise SEO rankings
```

Copy opener / talking points / full prep and **Save to notes** are manual. Saving notes records `sales_prep_saved`. Generations are not stored unless you save.

## How it works

```text
CLI ───────────────┐
                   │
PySide6 GUI ───────┤
                   ↓
          Application / Services
                   ↓
        Search / Lead Engine  +  optional AI sales prep (Groq)
                   ↓
 Google Places + optional digital-presence check
                   ↓
        SQLite + CSV / JSON
```

CLI
 ↓
Configuration / Presets / Geography
 ↓
Google Places Client
 ↓
Normalization
 ↓
Filtering + Lead Scoring
 ↓
CSV / JSON

`--coverage` changes search breadth. `--fields` changes the Places field mask / billing SKU. Those are separate knobs.

## Engineering highlights

- Cost-aware field masks with honest SKU labels (`essentials` / `pro` / `enterprise`)
- Text Search pagination that keeps the original query parameters
- Retries with exponential backoff, jitter, and `Retry-After` for 429/5xx only
- Deterministic lead scoring plus a separate digital-opportunity score
- Superficial digital-presence checks (timeouts, size limits, no crawling)
- Country / region / locality queries (Buenos Aires is an optional geo preset, not a global assumption)
- No persistent cache of Places content or HTML; Place IDs and user workflow metadata may be stored locally
- Local prospect pipeline with SQLite migrations, follow-ups, and activity history
- Optional Groq sales-prep copilot behind a provider interface, user-triggered, structured JSON
- Desktop GUI on the same engine, with cooperative cancel and offscreen tests
- HTTP-mocked pytest suite; Ruff and mypy in GitHub Actions without secrets

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Development:

```bash
python -m pip install -e ".[dev,gui]"
pytest
ruff check .
mypy src/leadfinder
```

## Configure Google Places

1. Enable **Places API (New)** in a Google Cloud project.
2. Create an API key restricted to Places API (New). For this CLI, prefer IP restrictions (server-side).
3. Copy `.env.example` to `.env` and replace the placeholder.

```env
GOOGLE_MAPS_API_KEY=your-places-api-key-here
```

`GOOGLE_PLACES_API_KEY` is also accepted. Keys are not taken as CLI flags.

Optional AI Sales Prep uses `GROQ_API_KEY` the same way. Discovery does not require it.

## Scoring, cost, and output

Default field profile is `enterprise` because `websiteUri` is required to find missing websites. Dropping phone numbers does not lower the SKU if `websiteUri` is still requested.

| Signal | Effect on lead score |
| --- | --- |
| No website | +40 |
| Weak / social / aggregator / unreachable / HTTP-only / parked | +20 |
| Operational | +15 |
| Has phone | +10 |
| Review activity | +5 to +10 |
| Closed temporarily / permanently | −20 / −50 |

Opportunity score uses the same commercial signals plus digital-opportunity points (for example +40 no website, +28 social-only). High ≥ 70, Medium ≥ 45, otherwise Low.

Permanently closed places are omitted by default. Exports go to `output/leads-<timestamp>.csv` and are not overwritten unless you pass `--force`. New columns include `presence_type`, `website_health`, `opportunity_score`, `opportunity_level`, and `qualification_reason`. Sample rows in `examples/` are synthetic.

## Compliance

This tool is independent software and is not a Google product. Place data comes from Google Maps / Places and is subject to [Google’s Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies) and Maps Platform terms. Place IDs, contact status, notes, tags, follow-ups, activity logs, and search-run metadata may be stored locally. Full Places records are not cached to skip billing. If you use AI Sales Prep, commercial fields of the selected lead are sent to Groq only after you click Generate. You are responsible for complying with applicable rules when contacting businesses.

## License

MIT. See `LICENSE`.

## Migration from the old scripts

| Old | New |
| --- | --- |
| `scraper_hoteles_places_api.py` | `leadfinder search` |
| `--business-preset` | `--business` |
| `--print-locations` | `leadfinder dry-run` |
| `--api-key` | env / `.env` only |
| Playwright Maps scraper | `legacy/` (unsupported, not installed by default) |
