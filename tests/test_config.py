from __future__ import annotations

import pytest

from leadfinder.config import SearchConfig
from leadfinder.errors import ConfigError


def test_plan_separates_coverage_from_billing() -> None:
    plan = SearchConfig(
        business="cafe",
        locations=["Mar del Plata"],
        region="Buenos Aires",
        country="AR",
        coverage="full",
        field_profile="pro",
    ).to_plan()
    assert plan.coverage == "full"
    assert "merienda" in plan.search_terms
    assert plan.billing_tier == "Text Search Pro"
    assert "websiteUri" not in plan.field_mask


def test_missing_location_is_an_error() -> None:
    with pytest.raises(ConfigError, match="location"):
        SearchConfig(business="cafe").to_plan()


def test_max_api_requests_caps_query_volume() -> None:
    plan = SearchConfig(
        business="cafe",
        locations=["A", "B"],
        coverage="budget",
        pages=3,
        max_requests=2,
    ).to_plan()
    assert plan.max_queries == 2
    assert plan.max_api_requests == 2
