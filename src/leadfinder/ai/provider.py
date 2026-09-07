from __future__ import annotations

import json
from typing import Protocol

from leadfinder.ai.models import (
    DEFAULT_GROQ_MODEL,
    REQUIRED_INSIGHTS_FIELDS,
    REQUIRED_RESULT_FIELDS,
    InsightsExplanation,
    SalesPrepRequest,
    SalesPrepResult,
)
from leadfinder.config import groq_api_key, groq_model_from_env
from leadfinder.errors import AINotConfiguredError, AIResponseValidationError


class AIProvider(Protocol):
    def generate_sales_prep(self, request: SalesPrepRequest) -> SalesPrepResult:
        """Return structured sales prep. Must not send outreach."""


def groq_model(override: str = "") -> str:
    if override.strip():
        return override.strip()
    return groq_model_from_env() or DEFAULT_GROQ_MODEL


def ai_configured() -> bool:
    """True when a Groq key is present. Does not call the network."""
    return bool(groq_api_key())


def parse_sales_prep_json(raw: str, *, prompt_version: str) -> SalesPrepResult:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise AIResponseValidationError(
            "AI returned an invalid structured response."
        ) from error
    if not isinstance(payload, dict):
        raise AIResponseValidationError("AI returned an invalid structured response.")
    missing = [key for key in REQUIRED_RESULT_FIELDS if key not in payload]
    if missing:
        raise AIResponseValidationError("AI returned an invalid structured response.")
    for key in ("opportunity_summary", "pitch_angle", "opening_message", "next_step"):
        if not str(payload.get(key) or "").strip():
            raise AIResponseValidationError("AI returned an invalid structured response.")

    def _strings(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    return SalesPrepResult(
        opportunity_summary=str(payload.get("opportunity_summary") or "").strip(),
        pitch_angle=str(payload.get("pitch_angle") or "").strip(),
        value_props=_strings(payload.get("value_props")),
        opening_message=str(payload.get("opening_message") or "").strip(),
        talking_points=_strings(payload.get("talking_points")),
        objections=_strings(payload.get("objections")),
        cautions=_strings(payload.get("cautions")),
        next_step=str(payload.get("next_step") or "").strip(),
        observed=_strings(payload.get("observed")),
        information_gaps=str(payload.get("information_gaps") or "").strip(),
        prompt_version=prompt_version,
    )


def parse_insights_json(raw: str, *, prompt_version: str) -> InsightsExplanation:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise AIResponseValidationError(
            "AI returned an invalid structured response."
        ) from error
    if not isinstance(payload, dict):
        raise AIResponseValidationError("AI returned an invalid structured response.")
    missing = [key for key in REQUIRED_INSIGHTS_FIELDS if key not in payload]
    if missing:
        raise AIResponseValidationError("AI returned an invalid structured response.")
    if not str(payload.get("summary") or "").strip():
        raise AIResponseValidationError("AI returned an invalid structured response.")

    def _strings(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    return InsightsExplanation(
        summary=str(payload.get("summary") or "").strip(),
        observed=_strings(payload.get("observed")),
        hypotheses=_strings(payload.get("hypotheses")),
        experiments=_strings(payload.get("experiments")),
        cautions=_strings(payload.get("cautions")),
        prompt_version=prompt_version,
    )


def require_ai_key() -> str:
    key = groq_api_key()
    if not key:
        raise AINotConfiguredError(
            "AI sales prep is not configured.\n\nSet GROQ_API_KEY to enable it."
        )
    return key
