# Security

LeadFinder stores data on the local machine. API keys are read from the environment, an optional developer `.env` in the working directory (never from the packaged install folder), or the OS credential store when `keyring` is available. Keys must never be committed, logged, or stored in SQLite / QSettings / workspace ZIP / JSON config.

## Reporting

Do not open a public issue that includes secrets, API keys, or personal data.

Use GitHub private vulnerability reporting if it is enabled on the repository. Otherwise open a public issue that describes the class of problem only (no keys, tokens, or customer data).

There is no separate security email published for this project.

## Scope notes

- Tests must mock network.
- Google Places payloads and website HTML are not persisted.
- Optional Groq calls send minimized fields only, after an explicit user action.
- Packaged Windows builds are unsigned. SmartScreen may warn. Do not disable antivirus. Heuristic scans of `dist/` are not a security proof.

