from __future__ import annotations

import os
from typing import Any

os.environ.pop("LEADFINDER_DB_PATH", None)
os.environ.pop("LEADFINDER_DATA_DIR", None)
os.environ.pop("LEADFINDER_SMOKE_EXIT", None)
os.environ.pop("LEADFINDER_PACKAGED_TEST", None)
os.environ.pop("LEADFINDER_KEYRING_ACCOUNT_PLACES", None)
os.environ.pop("LEADFINDER_TEST_PLACES_API_KEY", None)
os.environ.pop("LEADFINDER_TEST_GROQ_API_KEY", None)


def synthetic_place(
    place_id: str,
    name: str,
    *,
    website: str = "",
    phone: str = "+54 11 0000 0000",
    address: str = "100 Example Street, Example City",
    status: str = "OPERATIONAL",
    types: list[str] | None = None,
    primary_type: str = "cafe",
    maps_url: str = "https://maps.google.com/?cid=0",
    rating: float | None = 4.2,
    user_rating_count: int | None = 12,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": place_id,
        "displayName": {"text": name},
        "formattedAddress": address,
        "nationalPhoneNumber": phone,
        "websiteUri": website,
        "googleMapsUri": maps_url,
        "businessStatus": status,
        "types": types or ["cafe", "food"],
        "primaryType": primary_type,
    }
    if rating is not None:
        payload["rating"] = rating
    if user_rating_count is not None:
        payload["userRatingCount"] = user_rating_count
    return payload
