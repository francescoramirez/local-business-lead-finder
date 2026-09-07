from __future__ import annotations

from pathlib import Path

from leadfinder.application.service import LeadService
from leadfinder.storage.local_leads import LocalLeadStore

PRESETS = ("cafe", "hotel", "electrician", "bakery", "gym")
LOCATIONS = ("Example City", "North Town", "South Town", "Harbor")
PRESENCE = ("no_website", "has_website", "social_only", "weak_website")


def _seed(store: LocalLeadStore, n: int = 150) -> None:
    for index in range(n):
        place_id = f"ChIJ_SYNTH_E2E_{index:03d}"
        preset = PRESETS[index % len(PRESETS)]
        location = LOCATIONS[index % len(LOCATIONS)]
        presence = PRESENCE[index % len(PRESENCE)]
        store.mark_seen(
            place_id,
            label=f"Synthetic {index}",
            business_preset=preset,
            source_location=location,
            website_status=presence,
            opportunity_level="high" if index % 3 == 0 else "medium",
            opportunity_score=70 if index % 3 == 0 else 50,
        )
        if index % 5 == 0:
            store.set_contact_status(place_id, "contacted")
        if index % 7 == 0:
            store.set_contact_status(place_id, "interested")
        if index % 23 == 0:
            store.set_contact_status(place_id, "won")


def test_synthetic_workspace_flow_and_query_budget(tmp_path: Path) -> None:
    db = tmp_path / "e2e.db"
    store = LocalLeadStore(db)
    service = LeadService(store)
    campaign = service.create_campaign(name="E2E Example", business_preset="cafe")
    _seed(store, 150)
    ids = [f"ChIJ_SYNTH_E2E_{index:03d}" for index in range(150)]
    store.attach_leads(campaign.id, ids[:40])
    experiment = service.create_experiment(
        name="No website cafes",
        hypothesis="No-website cafes may convert differently than baseline.",
        business_preset="cafe",
        digital_presence="no_website",
        campaign_ids=[campaign.id],
    )

    queries = {"n": 0}

    def traced(_sql: str) -> None:
        queries["n"] += 1

    store._conn.set_trace_callback(traced)
    analytics = service.analytics_report(days=0)
    insights = service.insights_report(days=0)
    metrics = service.experiment_metrics(experiment, days=0)
    store._conn.set_trace_callback(None)

    assert analytics.historical.total_leads == 150
    assert insights.period_label
    assert metrics.experiment_id == experiment.id
    assert queries["n"] < 80

    backup = service.backup(tmp_path / "e2e-backup.db")
    zip_path = service.export_workspace(tmp_path / "e2e.zip")
    assert backup.exists()
    assert zip_path.exists()
    safety = service.restore(backup)
    assert safety.exists()
    after = service.analytics_report(days=0)
    assert after.historical.total_leads == analytics.historical.total_leads
    doctor = service.doctor()
    assert doctor.ok()
    store.close()


def test_thousands_of_leads_use_bounded_queries(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "many.db")
    service = LeadService(store)
    for index in range(2500):
        store.mark_seen(
            f"ChIJ_SYNTH_MANY_{index}",
            label=f"Lead {index}",
            business_preset="cafe",
            source_location="Example City",
            website_status="no_website" if index % 2 == 0 else "has_website",
            commit=False,
        )
    store._conn.commit()
    queries = {"n": 0}

    def traced(_sql: str) -> None:
        queries["n"] += 1

    store._conn.set_trace_callback(traced)
    report = service.analytics_report(days=0)
    service.insights_report(days=0)
    store._conn.set_trace_callback(None)
    assert report.historical.total_leads == 2500
    assert queries["n"] < 80
    store.close()
