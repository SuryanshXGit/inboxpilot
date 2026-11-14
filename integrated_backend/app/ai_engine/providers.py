"""Provider adapters, bounded retries and primary/fallback selection.

All HTTP calls use ``httpx`` directly so the integration does not depend on the
release cadence of separate vendor SDKs. The adapters share one narrow
interface, which makes adding or mocking a provider straightforward.

Security notes:
- API keys are read from settings at call time and are never logged.
- Response bodies are never logged; only provider name and HTTP status.
- Retries are bounded by ``AI_MAX_RETRIES`` and apply only to transient
  failures (timeouts, transport errors, HTTP 408/409/425/429/5xx).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.ai_engine.models import AIProviderUnavailable
from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider errors
# ---------------------------------------------------------------------------


class ProviderCallError(RuntimeError):
    """A provider call failed. Messages are safe to log."""

    transient: bool = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class ProviderTransientError(ProviderCallError):
    """Retryable: timeout, transport failure, rate limit or server error."""

    transient = True


class ProviderPermanentError(ProviderCallError):
    """Not retryable: bad credentials, invalid request or unsupported model."""


class ProviderConfigurationError(ProviderPermanentError):
    """Provider selected but its credentials or configuration are missing."""


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


async def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        raise ProviderTransientError("provider request timed out") from None
    except httpx.TransportError:
        raise ProviderTransientError("provider network error") from None

    if response.status_code >= 400:
        retry_after = _parse_retry_after(response.headers.get("retry-after"))
        transient = response.status_code in {408, 409, 425, 429} or response.status_code >= 500
        error_type = ProviderTransientError if transient else ProviderPermanentError
        raise error_type(
            f"provider returned HTTP {response.status_code}",
            status_code=response.status_code,
            retry_after=retry_after,
        )

    try:
        payload_json = response.json()
    except ValueError:
        raise ProviderTransientError("provider returned a malformed response envelope") from None

    if not isinstance(payload_json, dict):
        raise ProviderTransientError("provider returned an unexpected response envelope")
    return payload_json


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(0.0, min(seconds, 10.0))


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class BaseProvider:
    name = "base"
    # Provider-specific extras merged into the JSON request body.
    extra_payload: dict[str, Any] = {}

    def __init__(self, *, model: str, api_key: str, timeout: float) -> None:
        self.model = model
        self._api_key = api_key
        self.timeout = timeout

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        raise NotImplementedError


def _openai_compatible_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, *, model: str, api_key: str, timeout: float, base_url: str | None) -> None:
        super().__init__(model=model, api_key=api_key, timeout=timeout)
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            # JSON mode is supported by every current chat model. The
            # schema is enforced twice: in the prompt and by Pydantic.
            "response_format": {"type": "json_object"},
        }
        if self.extra_payload:
            body.update(self.extra_payload)

        payload = await _post_json(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            payload=body,
            timeout=self.timeout,
        )
        return _openai_compatible_text(payload)

# ---------------------------------------------------------------------------
# Groq (OpenAI-compatible endpoint; fallback by default)
# ---------------------------------------------------------------------------


class GroqProvider(OpenAIProvider):
    """Groq's OpenAI-compatible endpoint.

    ``gpt-oss`` models default to heavy reasoning, which takes a minute or more
    per request. Groq accepts ``reasoning_effort``, so a low setting keeps
    latency in the low seconds without hurting output quality.
    """

    name = "groq"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        timeout: float,
        base_url: str,
        reasoning_effort: str | None = None,
    ) -> None:
        super().__init__(model=model, api_key=api_key, timeout=timeout, base_url=base_url)
        self.extra_payload = (
            {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        )


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, *, model: str, api_key: str, timeout: float, base_url: str) -> None:
        super().__init__(model=model, api_key=api_key, timeout=timeout)
        self.base_url = base_url.rstrip("/")

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        payload = await _post_json(
            f"{self.base_url}/models/{self.model}:generateContent",
            headers={
                # Header keeps the key out of the URL (and out of logs).
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            payload={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_output_tokens,
                    "responseMimeType": "application/json",
                },
            },
            timeout=self.timeout,
        )
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return ""
        candidate = candidates[0]
        content = candidate.get("content") if isinstance(candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            return ""
        return "".join(
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )


# ---------------------------------------------------------------------------
# Factory and orchestration
# ---------------------------------------------------------------------------


def build_provider(name: str, *, config: Settings | None = None) -> BaseProvider:
    """Construct the adapter for ``name`` or raise a configuration error."""

    cfg = config or settings
    value = (name or "").strip().lower()

    if value == "openai":
        if not cfg.OPENAI_API_KEY:
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured")
        return OpenAIProvider(
            model=cfg.OPENAI_MODEL,
            api_key=cfg.OPENAI_API_KEY,
            timeout=cfg.AI_TIMEOUT_SECONDS,
            base_url=cfg.OPENAI_BASE_URL,
        )

    if value == "groq":
        if not cfg.GROQ_API_KEY:
            raise ProviderConfigurationError("GROQ_API_KEY is not configured")
        return GroqProvider(
            model=cfg.GROQ_MODEL,
            api_key=cfg.GROQ_API_KEY,
            timeout=cfg.AI_TIMEOUT_SECONDS,
            base_url=cfg.GROQ_BASE_URL,
            reasoning_effort=cfg.groq_reasoning_effort,
        )

    if value == "gemini":
        if not cfg.GEMINI_API_KEY:
            raise ProviderConfigurationError("GEMINI_API_KEY is not configured")
        return GeminiProvider(
            model=cfg.GEMINI_MODEL,
            api_key=cfg.GEMINI_API_KEY,
            timeout=cfg.AI_TIMEOUT_SECONDS,
            base_url=cfg.GEMINI_BASE_URL,
        )

    raise ProviderConfigurationError(f"Unknown AI provider: {value or '(empty)'}")


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    provider: str


def _provider_chain(cfg: Settings) -> list[str]:
    chain: list[str] = []
    if cfg.primary_provider:
        chain.append(cfg.primary_provider)
    if cfg.fallback_provider and cfg.fallback_provider not in chain:
        chain.append(cfg.fallback_provider)
    return chain


async def _call_with_retries(
    provider: BaseProvider,
    *,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],
    cfg: Settings,
) -> str:
    attempts = cfg.AI_MAX_RETRIES + 1
    for attempt in range(attempts):
        try:
            return await provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=json_schema,
                max_output_tokens=cfg.AI_MAX_OUTPUT_TOKENS,
                temperature=cfg.AI_TEMPERATURE,
            )
        except ProviderTransientError as exc:
            if attempt + 1 >= attempts:
                raise
            delay = min(
                cfg.AI_RETRY_BACKOFF_SECONDS * (2**attempt),
                10.0,
            )
            if exc.retry_after is not None:
                delay = max(delay, exc.retry_after)
            logger.info(
                "Transient AI provider failure (%s, HTTP %s); retrying in %.2fs (%d/%d)",
                provider.name,
                exc.status_code,
                delay,
                attempt + 1,
                attempts - 1,
            )
            if delay > 0:
                await asyncio.sleep(delay)
    raise ProviderTransientError("provider retry budget exhausted")


async def generate_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],
    config: Settings | None = None,
) -> ProviderResponse:
    """Call the primary provider, then the configured fallback once.

    Raises ``AIProviderUnavailable`` when no provider is configured or when
    every attempt fails. Never raises vendor-specific exceptions.
    """

    cfg = config or settings
    chain = _provider_chain(cfg)
    if not chain:
        raise AIProviderUnavailable("No AI provider is configured")

    for name in chain:
        try:
            provider = build_provider(name, config=cfg)
        except ProviderConfigurationError as exc:
            logger.warning("AI provider %s is not configured: %s", name, exc)
            continue

        try:
            text = await _call_with_retries(
                provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=json_schema,
                cfg=cfg,
            )
        except ProviderCallError as exc:
            logger.warning(
                "AI provider %s failed (%s): %s",
                name,
                type(exc).__name__,
                exc,
            )
            continue
        except Exception:
            # A vendor library must never take the API process down.
            logger.exception("Unexpected failure in AI provider %s", name)
            continue

        return ProviderResponse(text=text, provider=name)

    raise AIProviderUnavailable("All configured AI providers are unavailable")


def configured_providers(config: Settings | None = None) -> list[str]:
    """Return provider names that have credentials configured (no secrets)."""

    cfg = config or settings
    available: list[str] = []
    for name in ("openai", "groq", "gemini"):
        try:
            build_provider(name, config=cfg)
        except ProviderConfigurationError:
            continue
        available.append(name)
    return available
