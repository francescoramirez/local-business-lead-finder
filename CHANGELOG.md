# Changelog

All notable LeadFinder versions. Dates are omitted when they cannot be derived from the repository.

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
