from __future__ import annotations

import pytest

from leadfinder.errors import ConfigError
from leadfinder.geo_buenos_aires import CABA, buenos_aires_locations
from leadfinder.geography import build_query, normalize_country, resolve_locations


def test_caba_does_not_append_buenos_aires_province() -> None:
    query = build_query(
        "hotel",
        "Ciudad Autonoma de Buenos Aires",
        region="Buenos Aires",
        country="AR",
    )
    assert query == "hotel en Ciudad Autonoma de Buenos Aires, Argentina"
    assert "provincia de Buenos Aires" not in query


def test_mar_del_plata_uses_explicit_region_and_country() -> None:
    query = build_query(
        "cafe",
        "Mar del Plata",
        region="Buenos Aires",
        country="AR",
    )
    assert query == "cafe en Mar del Plata, Buenos Aires, Argentina"


def test_cordoba_is_not_forced_into_buenos_aires() -> None:
    query = build_query("cafe", "Cordoba", region="Cordoba", country="AR")
    assert query == "cafe en Cordoba, Cordoba, Argentina"
    assert "Buenos Aires" not in query


def test_other_country_is_supported() -> None:
    query = build_query("cafe", "Montevideo", region="", country="UY")
    assert query == "cafe en Montevideo, Uruguay"


def test_country_must_be_iso_code() -> None:
    with pytest.raises(ConfigError):
        normalize_country("Argentina")


def test_geo_preset_is_opt_in() -> None:
    only_explicit = resolve_locations(locations=["Rosario"], geo_preset="", coverage="budget")
    assert only_explicit == ["Rosario"]
    with_preset = resolve_locations(locations=[], geo_preset="buenos-aires", coverage="budget")
    assert CABA in with_preset
    assert with_preset.count(CABA) == 1


def test_buenos_aires_lists_have_no_structural_duplicates() -> None:
    for coverage in ("budget", "balanced", "full"):
        locations = buenos_aires_locations(coverage)
        normalized = [" ".join(item.lower().split()) for item in locations]
        assert len(normalized) == len(set(normalized))
        assert normalized.count("ciudad autonoma de buenos aires") == 1
