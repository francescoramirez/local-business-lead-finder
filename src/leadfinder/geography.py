from __future__ import annotations

from leadfinder.errors import ConfigError
from leadfinder.geo_buenos_aires import buenos_aires_locations

COUNTRY_NAMES: dict[str, str] = {
    "AR": "Argentina",
    "BO": "Bolivia",
    "BR": "Brasil",
    "CL": "Chile",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "EC": "Ecuador",
    "ES": "Espana",
    "GT": "Guatemala",
    "MX": "Mexico",
    "PA": "Panama",
    "PE": "Peru",
    "PY": "Paraguay",
    "UY": "Uruguay",
    "US": "United States",
    "VE": "Venezuela",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
}

LANGUAGE_BY_COUNTRY: dict[str, str] = {
    "AR": "es-419",
    "BO": "es-419",
    "CL": "es-419",
    "CO": "es-419",
    "CR": "es-419",
    "EC": "es-419",
    "ES": "es",
    "GT": "es-419",
    "MX": "es-419",
    "PA": "es-419",
    "PE": "es-419",
    "PY": "es-419",
    "UY": "es-419",
    "VE": "es-419",
    "BR": "pt-BR",
    "US": "en",
    "GB": "en",
    "UK": "en",
}

CABA_MARKERS = (
    "ciudad autonoma de buenos aires",
    "ciudad autónoma de buenos aires",
    "capital federal",
    "caba",
)

GEO_PRESETS = ("buenos-aires",)


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        item = raw.strip()
        if not item:
            continue
        key = " ".join(item.lower().split())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def split_csv_arg(value: str) -> list[str]:
    return unique(value.split(","))


def normalize_country(country: str) -> str:
    code = country.strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise ConfigError("Country must be a 2-letter code such as AR, UY, or US.")
    if code == "UK":
        return "GB"
    return code


def country_name(country: str) -> str:
    code = normalize_country(country)
    return COUNTRY_NAMES.get(code, code)


def language_for_country(country: str) -> str:
    code = normalize_country(country)
    return LANGUAGE_BY_COUNTRY.get(code, "en")


def is_caba(location: str) -> bool:
    normalized = " ".join(location.lower().split())
    return any(marker in normalized for marker in CABA_MARKERS)


def _region_already_present(location: str, region: str) -> bool:
    loc = " ".join(location.lower().split())
    reg = " ".join(region.lower().split())
    if not reg or loc == reg:
        return False
    return reg in loc


def build_query(
    search_term: str,
    location: str,
    *,
    region: str = "",
    country: str = "AR",
) -> str:
    """Build a Text Search query from term + locality + optional region + country.

    CABA is a city, not a Buenos Aires province locality. If the location is CABA
    and the region is Buenos Aires, the region is omitted.
    """
    term = search_term.strip()
    locality = location.strip()
    if not term or not locality:
        raise ConfigError("Both search term and location are required to build a query.")

    country_label = country_name(country)
    parts = [locality]
    region_label = region.strip()
    skip_region = is_caba(locality) and region_label.lower() in {
        "buenos aires",
        "provincia de buenos aires",
    }
    if region_label and not skip_region and not _region_already_present(locality, region_label):
        parts.append(region_label)
    if country_label.lower() not in locality.lower():
        parts.append(country_label)
    return f"{term} en {', '.join(parts)}"


def resolve_locations(
    *,
    locations: list[str],
    geo_preset: str = "",
    coverage: str = "budget",
) -> list[str]:
    resolved = unique(locations)
    preset = geo_preset.strip().lower()
    if preset:
        if preset not in GEO_PRESETS:
            known = ", ".join(GEO_PRESETS)
            raise ConfigError(f"Unknown geo preset '{geo_preset}'. Choose one of: {known}.")
        resolved.extend(buenos_aires_locations(coverage))
    return unique(resolved)
