from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from leadfinder.errors import ConfigError, MissingApiKeyError
from leadfinder.fields import DEFAULT_FIELD_PROFILE, FieldProfile, get_field_profile
from leadfinder.geography import (
    language_for_country,
    normalize_country,
    resolve_locations,
    split_csv_arg,
    unique,
)
from leadfinder.models import SearchPlan
from leadfinder.place_types import is_table_a_type
from leadfinder.presets import get_preset

API_KEY_ENV_VARS = ("GOOGLE_MAPS_API_KEY", "GOOGLE_PLACES_API_KEY")
MAX_PAGES = 3
MAX_PAGE_SIZE = 20
DEFAULT_OUTPUT_DIR = Path("output")


@dataclass
class SearchConfig:
    business: str = "hotel"
    locations: list[str] = field(default_factory=list)
    region: str = ""
    country: str = "AR"
    coverage: str = "budget"
    field_profile: str = DEFAULT_FIELD_PROFILE
    terms: list[str] = field(default_factory=list)
    place_type: str = ""
    geo_preset: str = ""
    page_size: int = 20
    pages: int = 1
    max_requests: int = 100
    delay: float = 1.0
    language_code: str = ""
    only_no_website: bool = False
    include_closed: bool = False
    analyze_websites: bool = False
    output: Path | None = None
    formats: tuple[str, ...] = ("csv",)
    force: bool = False
    seen_ids_path: Path | None = None

    def resolved_country(self) -> str:
        return normalize_country(self.country)

    def resolved_profile(self) -> FieldProfile:
        return get_field_profile(self.field_profile)

    def resolved_preset(self):
        return get_preset(self.business)

    def resolved_place_type(self) -> str:
        if self.place_type.strip():
            value = self.place_type.strip()
            if not is_table_a_type(value):
                raise ConfigError(
                    f"'{value}' is not a Places API (New) Table A type. "
                    "Leave --place-type empty to skip type filtering."
                )
            return value
        return self.resolved_preset().included_type

    def resolved_terms(self) -> list[str]:
        if self.terms:
            return unique(self.terms)
        return self.resolved_preset().terms_for(self.coverage)

    def resolved_locations(self) -> list[str]:
        locations = resolve_locations(
            locations=self.locations,
            geo_preset=self.geo_preset,
            coverage=self.coverage,
        )
        if not locations:
            raise ConfigError(
                "Provide --location or --geo-preset buenos-aires. "
                "The engine no longer assumes every search is in Buenos Aires."
            )
        return locations

    def resolved_language(self) -> str:
        if self.language_code.strip():
            return self.language_code.strip()
        return language_for_country(self.resolved_country())

    def resolved_region(self) -> str:
        if self.region.strip():
            return self.region.strip()
        if self.geo_preset.strip().lower() == "buenos-aires":
            return "Buenos Aires"
        return ""

    def validate_limits(self) -> None:
        if self.coverage not in {"budget", "balanced", "full"}:
            raise ConfigError("Coverage must be budget, balanced, or full.")
        if self.pages < 1 or self.pages > MAX_PAGES:
            raise ConfigError(f"pages must be between 1 and {MAX_PAGES}.")
        if self.page_size < 1 or self.page_size > MAX_PAGE_SIZE:
            raise ConfigError(f"page-size must be between 1 and {MAX_PAGE_SIZE}.")
        if self.max_requests < 1:
            raise ConfigError("max-requests must be at least 1.")
        if self.delay < 0:
            raise ConfigError("delay cannot be negative.")
        unknown_formats = [item for item in self.formats if item not in {"csv", "json"}]
        if unknown_formats:
            raise ConfigError("Format must be csv, json, or both.")

    def to_plan(self) -> SearchPlan:
        self.validate_limits()
        locations = self.resolved_locations()
        terms = self.resolved_terms()
        profile = self.resolved_profile()
        max_queries = len(locations) * len(terms)
        return SearchPlan(
            business=self.resolved_preset().name,
            included_type=self.resolved_place_type(),
            search_terms=terms,
            locations=locations,
            country=self.resolved_country(),
            region=self.resolved_region(),
            coverage=self.coverage,
            field_profile=profile.name,
            field_mask=profile.mask,
            billing_tier=profile.billing_tier,
            page_size=self.page_size,
            pages=self.pages,
            max_queries=max_queries,
            max_api_requests=min(self.max_requests, max_queries * self.pages),
            language_code=self.resolved_language(),
            only_no_website=self.only_no_website,
            include_closed=self.include_closed,
            analyze_websites=self.analyze_websites,
        )


def load_env_file() -> None:
    load_dotenv(dotenv_path=Path(".env"), override=False)


def get_api_key() -> str:
    load_env_file()
    for name in API_KEY_ENV_VARS:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise MissingApiKeyError(
        "Missing Places API key. Set GOOGLE_MAPS_API_KEY or GOOGLE_PLACES_API_KEY "
        "in the environment or a local .env file. See .env.example."
    )


def parse_locations(*values: str) -> list[str]:
    locations: list[str] = []
    for value in values:
        locations.extend(split_csv_arg(value))
    return unique(locations)
