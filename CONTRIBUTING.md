# Contributing

LeadFinder is a local-first, single-user tool. Keep it explainable. Do not add cloud SaaS, telemetry, or automated outreach.

## Install

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev,gui]"
```

## Checks

```bash
ruff check .
pytest
mypy src/leadfinder
python -m compileall src
```

GUI tests expect `QT_QPA_PLATFORM=offscreen`. Do not call Google, Groq, or live websites in tests.

## Pull requests

- Small, reviewable diffs.
- No API keys, real business fixtures, or generated caches.
- Do not rewrite the package from scratch.
- `legacy/` stays unsupported and out of default install / CI.
- Match existing error, logging, and persistence rules (no Places payloads or HTML in SQLite).
