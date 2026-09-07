"""Synthetic demo workspace. Never writes the default user database."""

from __future__ import annotations

from pathlib import Path

from leadfinder.errors import ConfigError
from leadfinder.paths import default_db_path, demo_db_path, is_user_database
from leadfinder.storage.local_leads import LocalLeadStore
from leadfinder.workflow import to_iso, utc_now

DEMO_NAMES = (
    "Amber Finch Bakery",
    "Blue Lantern Inn",
    "Cedar Quill Studio",
    "Driftwood Kettle Cafe",
    "Ember Maple Gym",
    "Foghorn Ledger Office",
    "Glass Orchard Hotel",
    "Harbor Needle Tailor",
    "Ivory Compass Clinic",
    "Juniper Loom Shop",
    "Kite & Copper Bar",
    "Linen Atlas Pharmacy",
    "Marble Finch Restaurant",
    "North Pebble Dental",
    "Otter Pine Workshop",
    "Paper Orchid Salon",
    "Quartz Harbor Cafe",
    "River Cinder Bakery",
    "Sandpiper Vault Gym",
    "Timber Quill Hotel",
    "Umber Sparrow Law",
    "Velvet Anchor Salon",
    "Willow Circuit Repair",
    "Yarrow Point Dentist",
    "Zinc Harbor Fitness",
)

PRESETS = (
    "cafe",
    "restaurant",
    "hotel",
    "gym",
    "beauty_salon",
    "dentist",
    "electrician",
    "plumber",
    "car_repair",
    "bar",
)
CITIES = ("Example Bay", "Harbor Town", "North Dunes", "Cedar Inlet")
PRESENCE = ("no_website", "social_only", "has_website", "link_aggregator", "unreachable")
STATUSES = ("new", "contacted", "interested", "follow_up", "won", "rejected")
PRIORITIES = ("high", "normal", "low", "ignore")


def seed_demo_database(path: Path, *, count: int = 80) -> Path:
    destination = path.expanduser().resolve()
    default = default_db_path().expanduser().resolve()
    if destination == default or is_user_database(destination):
        raise ConfigError(
            "Refusing to seed the default LeadFinder database. Pass an explicit --db path."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    for extra in (Path(str(destination) + "-wal"), Path(str(destination) + "-shm")):
        if extra.exists():
            extra.unlink()
    store = LocalLeadStore(destination)
    now = utc_now()
    stamp = to_iso(now)
    campaigns = [
        store.create_campaign(
            name="Demo Bay cafes",
            business_preset="cafe",
            location="Example Bay",
            notes="Synthetic demo campaign",
        ),
        store.create_campaign(
            name="Demo hotels",
            business_preset="hotel",
            location="Harbor Town",
        ),
        store.create_campaign(
            name="Demo local services",
            business_preset="electrician",
            location="Cedar Inlet",
        ),
    ]
    place_ids: list[str] = []
    total = max(60, min(count, 100))
    for index in range(total):
        name = DEMO_NAMES[index % len(DEMO_NAMES)]
        suffix = index // len(DEMO_NAMES) + 1
        label = f"{name} {suffix}"
        place_id = f"ChIJ_DEMO_{index:04d}"
        city = CITIES[index % len(CITIES)]
        preset = PRESETS[index % len(PRESETS)]
        status = STATUSES[index % len(STATUSES)]
        presence = PRESENCE[index % len(PRESENCE)]
        store.mark_seen(
            place_id,
            label=label,
            opportunity_level=("high", "medium", "low")[index % 3],
            opportunity_score=40 + (index % 50),
            has_phone=index % 3 != 0,
            business_preset=preset,
            source_location=city,
            region="Demo Province",
            country="AR",
            website_status=presence,
            campaign_id=campaigns[index % len(campaigns)].id,
        )
        store.set_manual_priority(place_id, PRIORITIES[index % len(PRIORITIES)])
        if status != "new":
            store.set_contact_status(place_id, status)
        if index % 5 == 0:
            store.set_follow_up(place_id, stamp)
        if index % 7 == 0:
            store.add_activity(place_id, "note", note="Demo follow-up note")
        place_ids.append(place_id)
    third = max(1, total // 3)
    store.attach_leads(campaigns[0].id, place_ids[:third])
    store.attach_leads(campaigns[1].id, place_ids[third : 2 * third])
    store.attach_leads(campaigns[2].id, place_ids[2 * third :])
    store.record_search(
        business_preset="cafe",
        location="Example Bay",
        region="Demo Province",
        country="AR",
        lead_count=third,
        high_opportunity_count=12,
        campaign_id=campaigns[0].id,
        request_count=18,
        field_profile="enterprise",
        pages=2,
        estimated_cost="0.63",
        pricing_version="google_places_text_search_new_2026_08",
        currency="USD",
        cost_status="known",
        billing_sku="text_search_enterprise",
    )
    store.record_search(
        business_preset="hotel",
        location="Harbor Town",
        region="Demo Province",
        country="AR",
        lead_count=third,
        high_opportunity_count=4,
        campaign_id=campaigns[1].id,
        cost_status="unknown",
    )
    experiment = store.create_experiment(
        name="Demo no-website vs site",
        hypothesis="No-website cafes may convert differently in this synthetic set.",
        business_preset="cafe",
        location="Example Bay",
        digital_presence="no_website",
    )
    store.attach_campaigns(experiment.id, [campaigns[0].id])
    store.create_template(
        name="No website",
        body=(
            "Hola {business_name}, vi que {business_type} en {location} no muestra un sitio "
            "propio. Podemos armar una web simple si les sirve."
        ),
        presence_type="no_website",
        language="Spanish",
    )
    store.create_template(
        name="Instagram-only",
        body=(
            "Hola {business_name}, noté presencia {presence_type} para {business_type} "
            "en {location}. Si quieren, preparamos un sitio que complemente eso."
        ),
        presence_type="social_only",
        language="Spanish",
    )
    store.close()
    return destination


def ensure_demo_database(*, reset: bool = False) -> Path:
    path = demo_db_path()
    if reset or not path.exists():
        return seed_demo_database(path)
    return path
