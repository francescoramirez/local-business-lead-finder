# Screenshot instructions

Do not add fabricated UI renders. Capture the real desktop app at **1366×768**.

```bash
python -m pip install -e ".[gui]"
leadfinder demo-data --db ./demo-leadfinder.db
# Open the GUI against that file only if you swap the workspace yourself.
# The command refuses the default user database.
# Then: leadfinder gui
```

Suggested captures (save as PNG in this folder):

| File | What to show |
| --- | --- |
| `search.png` | Search panel with cost preview (1/2/3 pages) and a dry-run summary |
| `pipeline.png` | Pipeline columns with mixed statuses |
| `analytics.png` | Learn → Analytics including campaign API estimate |
| `insights.png` | Learn → Insights |
| `costs.png` | Search cost preview plus campaign estimate text |

Owner checklist: Search, cost preview, results, priority, Undo, pitch template, Compare selected, Pipeline, Analytics, Insights.
