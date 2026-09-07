from __future__ import annotations

import io
import json
from email.message import EmailMessage
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from leadfinder.ai.groq_provider import GroqProvider
from leadfinder.ai.models import DEFAULT_GROQ_MODEL, PROMPT_VERSION, SalesPrepRequest
from leadfinder.ai.prompts import SYSTEM_PROMPT_V1, build_user_prompt, system_prompt
from leadfinder.ai.provider import (
    ai_configured,
    groq_model,
    parse_sales_prep_json,
    require_ai_key,
)
from leadfinder.ai.service import assert_minimized, build_sales_prep_request, generate_sales_prep
from leadfinder.application.service import LeadService, merge_local_state
from leadfinder.errors import (
    AIAuthError,
    AINotConfiguredError,
    AIRateLimitError,
    AIRequestError,
    AIResponseValidationError,
    AITimeoutError,
)
from leadfinder.models import ManagedLead
from leadfinder.normalize import place_to_lead
from leadfinder.scoring import score_lead
from leadfinder.storage.local_leads import LocalLeadStore
from tests.conftest import synthetic_place

VALID_JSON = {
    "opportunity_summary": "Strong local activity with 238 reviews, social-only web presence.",
    "pitch_angle": "Offer a standalone site as a complement to Instagram.",
    "value_props": ["Menu without social login", "Local search presence"],
    "opening_message": "Hola, vi que tienen una presencia activa en Instagram...",
    "talking_points": ["Own the web presence", "Direct inquiries"],
    "objections": ["Instagram is enough"],
    "cautions": ["Do not promise SEO rankings"],
    "next_step": "Ask if they want a simple site that complements Instagram.",
    "observed": ["Social-only presence", "238 reviews", "Operational"],
    "information_gaps": "No website HTML was reviewed.",
}


def _cafe_managed() -> ManagedLead:
    lead = score_lead(
        place_to_lead(
            synthetic_place(
                "ChIJ_SYNTHETIC_CAFE",
                "Cafe Example",
                website="https://instagram.com/cafeexample",
                phone="+54 11 5555 0000",
                rating=4.6,
                user_rating_count=238,
            ),
            source_query="cafe en Example City",
            location="Example City",
            search_term="cafe",
            business_preset="cafe",
            place_type="cafe",
            country="AR",
            region="Example",
        )
    )
    lead.website_status = "social_only"
    score_lead(lead)
    return ManagedLead(lead=lead, notes="Wants a simple site", tags="priority")


def _cafe_item(tmp_path: Path) -> tuple[ManagedLead, LocalLeadStore]:
    lead = _cafe_managed().lead
    store = LocalLeadStore(tmp_path / "leads.db")
    item = merge_local_state([lead], store)[0]
    item.notes = "Wants a simple site"
    item.tags = "priority"
    return item, store


def _request() -> SalesPrepRequest:
    return build_sales_prep_request(_cafe_managed(), language="Spanish")


def _ok_opener(payload: dict | None = None):
    body = json.dumps(
        {"choices": [{"message": {"content": json.dumps(payload or VALID_JSON)}}]}
    ).encode()

    class Response:
        def read(self) -> bytes:
            return body

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(request, timeout=None):  # noqa: ANN001
        opener.calls.append(request)
        return Response()

    opener.calls = []  # type: ignore[attr-defined]
    return opener


def _http_error(status: int, body: bytes = b"{}") -> HTTPError:
    return HTTPError(
        "https://api.groq.com/openai/v1/chat/completions",
        status,
        "error",
        EmailMessage(),
        io.BytesIO(body),
    )


def test_sales_prep_request_omits_phone_and_ids() -> None:
    item = _cafe_managed()
    request = build_sales_prep_request(item, language="Spanish")
    payload = request.to_payload()
    assert_minimized(payload)
    assert "phone" not in payload
    assert "place_id" not in payload
    assert "api_key" not in payload
    blob = json.dumps(payload)
    assert item.lead.phone not in blob
    assert "ChIJ_SYNTHETIC_CAFE" not in blob
    assert "+54" not in blob
    assert "Cafe Example" in payload["name"]
    assert payload["review_count"] == 238
    assert payload["rating"] == 4.6
    assert payload["digital_presence"] == "Social only"


def test_user_prompt_is_structured_signals_not_html() -> None:
    prompt = build_user_prompt(_request())
    assert "html" not in prompt.lower()
    assert "<" not in prompt
    assert "GROQ_API_KEY" not in prompt
    assert "gsk_" not in prompt
    assert PROMPT_VERSION in prompt
    assert "Cafe Example" in prompt


def test_anti_hallucination_prompt_contains_constraints() -> None:
    text = system_prompt()
    assert text == SYSTEM_PROMPT_V1
    for needle in (
        "Do not invent facts",
        "employees",
        "revenue",
        "customers",
        "technologies",
        "website problems",
        "personal attributes",
        "observed signals from suggestions",
        "Do not promise SEO",
        "suggested drafts",
        "selected_template",
    ):
        assert needle.lower() in text.lower() or needle in text


def test_parse_valid_json_and_fenced_block() -> None:
    result = parse_sales_prep_json(json.dumps(VALID_JSON), prompt_version="sales_prep_v1")
    assert result.opening_message.startswith("Hola")
    fenced = parse_sales_prep_json(
        "```json\n" + json.dumps(VALID_JSON) + "\n```",
        prompt_version="sales_prep_v1",
    )
    assert fenced.pitch_angle == result.pitch_angle


def test_malformed_json_and_missing_fields() -> None:
    with pytest.raises(AIResponseValidationError):
        parse_sales_prep_json("{not json", prompt_version="sales_prep_v1")
    broken = dict(VALID_JSON)
    del broken["opening_message"]
    with pytest.raises(AIResponseValidationError):
        parse_sales_prep_json(json.dumps(broken), prompt_version="sales_prep_v1")
    empty = dict(VALID_JSON)
    empty["opportunity_summary"] = "  "
    with pytest.raises(AIResponseValidationError):
        parse_sales_prep_json(json.dumps(empty), prompt_version="sales_prep_v1")


def test_provider_config_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("leadfinder.config.load_env_file", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    assert ai_configured() is False
    with pytest.raises(AINotConfiguredError):
        require_ai_key()
    assert groq_model() == DEFAULT_GROQ_MODEL
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testfakekey1234567890")
    monkeypatch.setenv("GROQ_MODEL", "llama-custom")
    assert ai_configured() is True
    assert groq_model() == "llama-custom"
    assert groq_model("override-model") == "override-model"


def test_groq_success_and_payload_has_no_secret() -> None:
    opener = _ok_opener()
    provider = GroqProvider(
        "gsk_testfakekey1234567890",
        model=DEFAULT_GROQ_MODEL,
        opener=opener,
        sleep=lambda _delay: None,
    )
    result = provider.generate_sales_prep(_request())
    assert result.next_step
    request = opener.calls[0]
    body = json.loads(request.data.decode())
    assert "gsk_" not in json.dumps(body)
    assert "+54" not in json.dumps(body)
    assert body["max_tokens"] == 800
    assert body["temperature"] == 0.3
    assert body["response_format"] == {"type": "json_object"}


def test_groq_401_is_not_retried() -> None:
    calls = {"n": 0}

    def opener(request, timeout=None):  # noqa: ANN001
        calls["n"] += 1
        raise _http_error(401, b'{"error":"invalid_api_key"}')

    provider = GroqProvider("bad", model="x", opener=opener, sleep=lambda _delay: None)
    with pytest.raises(AIAuthError):
        provider.generate_sales_prep(_request())
    assert calls["n"] == 1


def test_groq_400_is_not_retried() -> None:
    calls = {"n": 0}

    def opener(request, timeout=None):  # noqa: ANN001
        calls["n"] += 1
        raise _http_error(400, b'{"error":{"message":"The model does not exist"}}')

    provider = GroqProvider("key", model="missing-model", opener=opener, sleep=lambda _delay: None)
    with pytest.raises(AIRequestError, match="model"):
        provider.generate_sales_prep(_request())
    assert calls["n"] == 1


def test_groq_429_retries_then_succeeds() -> None:
    calls = {"n": 0}

    class Response:
        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(VALID_JSON)}}]}
            ).encode()

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(request, timeout=None):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(429, b'{"error":"rate"}')
        return Response()

    provider = GroqProvider(
        "key", model="x", opener=opener, max_retries=2, sleep=lambda _delay: None
    )
    result = provider.generate_sales_prep(_request())
    assert result.opening_message
    assert calls["n"] == 3


def test_groq_429_exhausted() -> None:
    def opener(request, timeout=None):  # noqa: ANN001
        raise _http_error(429)

    provider = GroqProvider(
        "key", model="x", opener=opener, max_retries=1, sleep=lambda _delay: None
    )
    with pytest.raises(AIRateLimitError):
        provider.generate_sales_prep(_request())


def test_groq_timeout() -> None:
    def opener(request, timeout=None):  # noqa: ANN001
        raise TimeoutError()

    provider = GroqProvider(
        "key", model="x", opener=opener, max_retries=0, sleep=lambda _delay: None
    )
    with pytest.raises(AITimeoutError):
        provider.generate_sales_prep(_request())


def test_groq_malformed_message() -> None:
    class Response:
        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "not-json"}}]}).encode()

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    provider = GroqProvider("key", model="x", opener=lambda *_a, **_k: Response(), max_retries=0)
    with pytest.raises(AIResponseValidationError):
        provider.generate_sales_prep(_request())


def test_groq_empty_choices() -> None:
    class Response:
        def read(self) -> bytes:
            return json.dumps({"choices": []}).encode()

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    provider = GroqProvider("key", model="x", opener=lambda *_a, **_k: Response(), max_retries=0)
    with pytest.raises(AIResponseValidationError):
        provider.generate_sales_prep(_request())


def test_network_error() -> None:
    def opener(request, timeout=None):  # noqa: ANN001
        raise URLError("connection refused")

    provider = GroqProvider("key", model="x", opener=opener, max_retries=0)
    from leadfinder.errors import AINetworkError

    with pytest.raises(AINetworkError):
        provider.generate_sales_prep(_request())


class _FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate_sales_prep(self, request: SalesPrepRequest):
        self.calls += 1
        from leadfinder.ai.models import SalesPrepResult

        return SalesPrepResult(
            opportunity_summary="Summary",
            pitch_angle="Angle",
            value_props=["Prop"],
            opening_message="Hola draft",
            talking_points=["Point"],
            objections=["Maybe later"],
            cautions=["Do not overclaim"],
            next_step="Call after review",
            observed=["Social only"],
        )


def test_service_prepare_and_save_activity(tmp_path: Path) -> None:
    item, store = _cafe_item(tmp_path)
    fake = _FakeProvider()
    service = LeadService(store, ai_provider=fake)
    result = service.prepare_sales(item, language="Spanish")
    assert fake.calls == 1
    assert result.opening_message == "Hola draft"
    updated = service.save_sales_prep(item, result)
    assert "AI sales prep" in updated.notes
    types = [row.activity_type for row in service.activities(item.lead.place_id)]
    assert "sales_prep_saved" in types
    store.close()
    restored = LocalLeadStore(tmp_path / "leads.db")
    state = restored.get(item.lead.place_id)
    assert state is not None
    assert "Hola draft" in state.notes
    restored.close()


def test_generate_sales_prep_uses_injected_provider() -> None:
    item = _cafe_managed()
    fake = _FakeProvider()
    generate_sales_prep(item, language="English", provider=fake)
    assert fake.calls == 1


def test_groq_insights_uses_aggregates_only() -> None:
    opener = _ok_opener(
        {
            "summary": "No-website segments converted higher.",
            "observed": ["50% vs 35% baseline"],
            "hypotheses": ["Missing websites may correlate with interest"],
            "experiments": ["Run a focused no-website campaign"],
            "cautions": ["Do not infer causality"],
        }
    )
    provider = GroqProvider(
        "test-key",
        model="x",
        opener=opener,
        max_retries=0,
    )
    result = provider.generate_insights(
        {"baseline_contact_to_interest": 35.0, "baseline_n": 40},
        language="Spanish",
    )
    assert "higher" in result.summary.lower()
    body = opener.calls[0].data.decode("utf-8")
    assert "place_id" not in body
    assert "test-key" not in body
    assert "analytics_insights_v1" in body
