# Testing

Tests live in `tests/` and must not use the network.

- HTTP for Places and Groq is mocked (`tests/http.py`, fake openers).
- Website analysis tests use local fixtures, not live fetches.
- GUI smoke tests require PySide6 and `QT_QPA_PLATFORM=offscreen`.
- Desktop tests cover runtime paths, credentials precedence, onboarding flags, demo isolation, Settings/About, and packaging spec text.
- Migration tests open synthetic SQLite files from schema v1 through current.
- Portability tests cover backup/restore, invalid files, and workspace ZIP merge.
- `test_e2e_synthetic.py` builds a temporary synthetic workspace (never real businesses).

```bash
pytest
QT_QPA_PLATFORM=offscreen pytest tests/test_gui_smoke.py
```
