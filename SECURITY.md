# Security

LeadFinder stores data on the local machine and reads API keys from the environment or a local `.env` file. Keys must never be committed, logged, or stored in SQLite / QSettings.

## Reporting

Do not open a public issue that includes secrets, API keys, or personal data.

Use GitHub private vulnerability reporting if it is enabled on the repository. Otherwise open a public issue that describes the class of problem only (no keys, tokens, or customer data).

There is no separate security email published for this project.

## Scope notes

- Tests must mock network.
- Google Places payloads and website HTML are not persisted.
- Optional Groq calls send minimized fields only, after an explicit user action.
