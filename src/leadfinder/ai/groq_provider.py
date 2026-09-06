from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from leadfinder.ai.models import (
    MAX_OUTPUT_TOKENS,
    REQUEST_TIMEOUT,
    TEMPERATURE,
    SalesPrepRequest,
    SalesPrepResult,
)
from leadfinder.ai.prompts import build_user_prompt, system_prompt
from leadfinder.ai.provider import parse_sales_prep_json, require_ai_key
from leadfinder.errors import (
    AIAuthError,
    AINetworkError,
    AIRateLimitError,
    AIRequestError,
    AIResponseValidationError,
    AITimeoutError,
    redact_secrets,
)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
TRANSIENT = {429, 500, 502, 503, 504}


class GroqProvider:
    """Groq OpenAI-compatible chat completions. One explicit generation per call."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str,
        timeout: float = REQUEST_TIMEOUT,
        max_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else require_ai_key()
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep
        self._opener = opener or urllib.request.urlopen

    def generate_sales_prep(self, request: SalesPrepRequest) -> SalesPrepResult:
        body = json.dumps(
            {
                "model": self.model,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": build_user_prompt(request)},
                ],
            }
        ).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                raw = self._post(body)
                content = _message_content(raw)
                return parse_sales_prep_json(content, prompt_version=request.prompt_version)
            except (AIRateLimitError, AINetworkError, AITimeoutError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    raise
                self._sleep(min(8.0, 1.5 * (2**attempt)))
            except AIAuthError:
                raise
        assert last_error is not None
        raise last_error

    def _post(self, body: bytes) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "leadfinder/0.5.0 (sales-prep)",
        }
        request = urllib.request.Request(GROQ_CHAT_URL, data=body, headers=headers, method="POST")
        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError as error:
            raise AITimeoutError("AI provider timed out.") from error
        except urllib.error.HTTPError as error:
            status = error.code
            detail = redact_secrets(error.read().decode("utf-8", errors="replace")[:400])
            if status in {401, 403}:
                raise AIAuthError("AI API key invalid.") from error
            if status == 429:
                raise AIRateLimitError("AI provider rate limit.") from error
            if status in {400, 404}:
                if "model" in detail.lower():
                    raise AIRequestError("The configured AI model was not found.") from error
                raise AIRequestError("AI provider rejected the request.") from error
            if status in TRANSIENT:
                raise AINetworkError("Could not reach AI provider.") from error
            raise AIRequestError(f"AI provider rejected the request ({status}).") from error
        except json.JSONDecodeError as error:
            raise AIResponseValidationError(
                "AI returned an invalid structured response."
            ) from error
        except urllib.error.URLError as error:
            reason = str(error.reason).lower()
            if "timed out" in reason:
                raise AITimeoutError("AI provider timed out.") from error
            raise AINetworkError("Could not reach AI provider.") from error
        if not isinstance(payload, dict):
            raise AINetworkError("Could not reach AI provider.")
        return payload


def _message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AINetworkError("AI provider returned an empty response.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise AINetworkError("AI provider returned an empty response.")
    return str(message.get("content") or "")
