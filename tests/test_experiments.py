from __future__ import annotations

from pathlib import Path

from leadfinder.application.service import LeadService
from leadfinder.experiments import evaluate_experiment, target_label
from leadfinder.storage.local_leads import LocalLeadStore


def _seed_contacts(store: LocalLeadStore, prefix: str, *, interested: int, contacted: int) -> None:
    for index in range(interested):
        place_id = f"ChIJ_SYNTH_{prefix}_I_{index}"
        store.mark_seen(
            place_id,
            label=f"Lead {prefix} {index}",
            business_preset="cafe",
            source_location="Example City",
            website_status="no_website",
            opportunity_level="high",
        )
        store.set_contact_status(place_id, "contacted")
        store.set_contact_status(place_id, "interested")
    for index in range(contacted):
        place_id = f"ChIJ_SYNTH_{prefix}_C_{index}"
        store.mark_seen(
            place_id,
            label=f"Lead {prefix} c {index}",
            business_preset="cafe",
            source_location="Example City",
            website_status="no_website",
            opportunity_level="high",
        )
        store.set_contact_status(place_id, "contacted")


def test_experiment_insufficient_then_above_baseline(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "exp.db")
    service = LeadService(store)
    experiment = service.create_experiment(
        name="Cafes without websites",
        hypothesis="Businesses without standalone websites may show higher contact->interest.",
        business_preset="cafe",
        digital_presence="no_website",
    )
    assert experiment.status == "draft"
    assert "Cafe" in target_label(experiment)
    metrics = service.experiment_metrics(experiment, days=0)
    assert metrics.evaluation == "Insufficient data"

    _seed_contacts(store, "A", interested=8, contacted=8)
    _seed_contacts(store, "B", interested=2, contacted=18)
    metrics = service.experiment_metrics(experiment, days=0)
    assert metrics.sample >= 5
    assert metrics.evaluation in {"Above baseline", "Near baseline", "Below baseline"}
    updated = service.update_experiment(experiment.id, status="active", observations="n growing")
    assert updated.status == "active"
    store.close()


def test_evaluate_experiment_uses_campaign_scope(tmp_path: Path) -> None:
    store = LocalLeadStore(tmp_path / "exp2.db")
    service = LeadService(store)
    campaign = service.create_campaign(
        name="Focus",
        business_preset="cafe",
        location="Example City",
    )
    experiment = service.create_experiment(
        name="Scoped",
        business_preset="cafe",
        digital_presence="no_website",
        campaign_ids=[campaign.id],
    )
    _seed_contacts(store, "OUT", interested=10, contacted=0)
    store.attach_leads(campaign.id, [])
    metrics = evaluate_experiment(
        experiment,
        store.load_lead_facts(),
        service.analytics_report(days=0).contact_to_interest,
        period_label="All time",
        campaign_ids=frozenset({campaign.id}),
    )
    assert metrics.evaluation == "Insufficient data"
    store.close()
