from __future__ import annotations

import pytest

from leadfinder.errors import ConfigError
from leadfinder.place_types import is_table_a_type
from leadfinder.presets import PRESETS, get_preset, list_presets


def test_expected_presets_exist() -> None:
    expected = {
        "hotel",
        "cafe",
        "restaurant",
        "bar",
        "gym",
        "beauty_salon",
        "dentist",
        "real_estate_agency",
        "car_repair",
        "technical_service",
        "electrician",
        "plumber",
        "locksmith",
        "painter",
        "roofing_contractor",
        "laundry",
        "moving_company",
        "hardware_store",
    }
    assert expected <= set(PRESETS)


def test_preset_types_are_table_a_or_empty() -> None:
    for preset in list_presets():
        if preset.included_type:
            assert is_table_a_type(preset.included_type)


def test_coverage_selects_terms_without_changing_type() -> None:
    cafe = get_preset("cafe")
    assert cafe.included_type == "cafe"
    assert cafe.terms_for("budget") == ["cafe"]
    assert "cafeteria" in cafe.terms_for("balanced")
    assert "merienda" in cafe.terms_for("full")


def test_unknown_preset_fails() -> None:
    with pytest.raises(ConfigError):
        get_preset("spaceship")
