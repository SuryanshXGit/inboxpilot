"""AI-engine unit tests.

Every provider is mocked; no network calls and no API credits are consumed.
The tests cover success, retries, fallback, malformed output, one repair,
schema validation and missing credentials.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.ai_engine import evaluate_answer, generate_lesson, generate_quiz
from app.ai_engine import providers
from app.ai_engine.models import (
    AIOutputInvalid,
    AIProviderUnavailable,
    EvaluationResult,
    LessonResult,
    QuizQuestion,
    QuizResult,
)
from app.ai_engine.providers import (
    ProviderPermanentError,
    ProviderTransientError,
)
from app.core.config import settings

LESSON_PAYLOAD = {
    "title": "Adding numbers",
    "explanation": "Two plus two equals four.",
    "key_points": ["Numbers can be added", "The result is called a sum"],
    "examples": ["2 + 2 = 4"],
    "check_for_understanding": "What is 3 + 1?",
    "suggested_next_topic": "Subtraction",
}

QUIZ_PAYLOAD = {
    "topic": "arithmetic",
    "questions": [
        {
            "question": "What is 2 + 2?",
            "options": ["3", "4", "5", "6"],
            "correct_option_index": 1,
            "explanation": "2 + 2 = 4.",
            "difficulty": "easy",
        },
        {
            "question": "What is 3 + 1?",
            "options": ["2", "3", "4", "5"],
            "correct_option_index": 2,
            "explanation": "3 + 1 = 4.",
            "difficulty": "easy",
        },
    ],
}

EVALUATION_PAYLOAD = {
    "is_correct": True,
    "score": 0.9,
    "feedback": "Correct, with clear reasoning.",
    "misconception": None,
    "next_step": "Try a two-digit addition problem.",
}

LESSON_JSON = json.dumps(LESSON_PAYLOAD)
QUIZ_JSON = json.dumps(QUIZ_PAYLOAD)
EVALUATION_JSON = json.dumps(EVALUATION_PAYLOAD)


class FakeProvider:
    """Deterministic provider double that records every call."""

    name = "fake"

    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.outputs) - 1)
        output = self.outputs[index]
        if isinstance(output, Exception):
            raise output
        return output


def _install_providers(
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, FakeProvider],
) -> None:
    def fake_build_provider(name: str, *, config: Any = None) -> FakeProvider:
        if name not in mapping:
            raise providers.ProviderConfigurationError(f"{name} is not configured")
        return mapping[name]

    monkeypatch.setattr(providers, "build_provider", fake_build_provider)


@pytest.fixture(autouse=True)
def _ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_PRIMARY_PROVIDER", "openai")
    monkeypatch.setattr(settings, "AI_FALLBACK_PROVIDER", "none")
    monkeypatch.setattr(settings, "AI_MAX_RETRIES", 1)
    monkeypatch.setattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq-key")


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_generate_lesson_returns_validated_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider([LESSON_JSON])
    _install_providers(monkeypatch, {"openai": primary})

    result = await generate_lesson(
        material_text="Two plus two equals four.",
        topic="addition",
        student_level="beginner",
        learning_goal="Learn addition",
        conversation_history=[],
    )

    assert isinstance(result, LessonResult)
    assert result.title == "Adding numbers"
    assert result.key_points
    assert len(primary.calls) == 1
    assert "Two plus two equals four." in primary.calls[0]["user_prompt"]
    assert "Return only valid JSON" in primary.calls[0]["system_prompt"]


async def test_generate_quiz_returns_validated_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider([QUIZ_JSON])
    _install_providers(monkeypatch, {"openai": primary})

    result = await generate_quiz(
        material_text="2 + 2 = 4",
        topic="arithmetic",
        difficulty="easy",
        count=2,
    )

    assert isinstance(result, QuizResult)
    assert len(result.questions) == 2
    assert all(len(question.options) == 4 for question in result.questions)
    assert result.questions[0].correct_option_index == 1


async def test_evaluate_answer_returns_validated_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider([EVALUATION_JSON])
    _install_providers(monkeypatch, {"openai": primary})

    result = await evaluate_answer(
        question="What is 2 + 2?",
        expected_answer="4",
        student_answer="4",
        rubric="Full credit for 4.",
    )

    assert isinstance(result, EvaluationResult)
    assert result.is_correct is True
    assert result.score == 0.9
    assert result.misconception is None


# ---------------------------------------------------------------------------
# Retries, fallback and provider failure
# ---------------------------------------------------------------------------


async def test_transient_error_is_retried_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider([ProviderTransientError("timeout"), LESSON_JSON])
    _install_providers(monkeypatch, {"openai": primary})

    result = await generate_lesson(material_text="2 + 2 = 4")

    assert isinstance(result, LessonResult)
    assert len(primary.calls) == 2


async def test_permanent_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider([ProviderPermanentError("bad credentials")])
    _install_providers(monkeypatch, {"openai": primary})

    with pytest.raises(AIProviderUnavailable):
        await generate_lesson(material_text="2 + 2 = 4")

    assert len(primary.calls) == 1


async def test_retry_budget_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider([ProviderTransientError("rate limited")])
    _install_providers(monkeypatch, {"openai": primary})

    with pytest.raises(AIProviderUnavailable):
        await generate_lesson(material_text="2 + 2 = 4")

    # AI_MAX_RETRIES=1 means one initial attempt plus one retry, never more.
    assert len(primary.calls) == 2


async def test_fallback_provider_is_used_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_FALLBACK_PROVIDER", "groq")
    primary = FakeProvider([ProviderTransientError("primary down")])
    fallback = FakeProvider([LESSON_JSON])
    _install_providers(monkeypatch, {"openai": primary, "groq": fallback})

    result = await generate_lesson(material_text="2 + 2 = 4")

    assert isinstance(result, LessonResult)
    assert len(primary.calls) == 2
    assert len(fallback.calls) == 1


async def test_all_providers_unavailable_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_FALLBACK_PROVIDER", "groq")
    primary = FakeProvider([ProviderTransientError("primary down")])
    fallback = FakeProvider([ProviderTransientError("fallback down")])
    _install_providers(monkeypatch, {"openai": primary, "groq": fallback})

    with pytest.raises(AIProviderUnavailable):
        await generate_lesson(material_text="2 + 2 = 4")


async def test_missing_credentials_raise_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(settings, "AI_FALLBACK_PROVIDER", "none")

    with pytest.raises(AIProviderUnavailable):
        await generate_lesson(material_text="2 + 2 = 4")


# ---------------------------------------------------------------------------
# Output validation and repair
# ---------------------------------------------------------------------------


async def test_malformed_output_is_repaired_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider(["not json at all", LESSON_JSON])
    _install_providers(monkeypatch, {"openai": primary})

    result = await generate_lesson(material_text="2 + 2 = 4")

    assert isinstance(result, LessonResult)
    assert len(primary.calls) == 2


async def test_malformed_output_after_repair_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider(["not json", "still not json"])
    _install_providers(monkeypatch, {"openai": primary})

    with pytest.raises(AIOutputInvalid):
        await generate_lesson(material_text="2 + 2 = 4")

    assert len(primary.calls) == 2


async def test_wrong_option_count_after_repair_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_quiz = json.dumps(
        {
            "topic": "arithmetic",
            "questions": [
                {
                    "question": "What is 2 + 2?",
                    "options": ["3", "4", "5"],
                    "correct_option_index": 1,
                    "explanation": "2 + 2 = 4.",
                    "difficulty": "easy",
                }
            ],
        }
    )
    primary = FakeProvider([invalid_quiz, invalid_quiz])
    _install_providers(monkeypatch, {"openai": primary})

    with pytest.raises(AIOutputInvalid):
        await generate_quiz(
            material_text="2 + 2 = 4",
            topic="arithmetic",
            difficulty="easy",
            count=1,
        )

    assert len(primary.calls) == 2


async def test_out_of_range_score_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_evaluation = json.dumps({**EVALUATION_PAYLOAD, "score": 10})
    primary = FakeProvider([invalid_evaluation, invalid_evaluation])
    _install_providers(monkeypatch, {"openai": primary})

    with pytest.raises(AIOutputInvalid):
        await evaluate_answer(
            question="What is 2 + 2?",
            expected_answer="4",
            student_answer="4",
            rubric="",
        )


async def test_markdown_fenced_json_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = FakeProvider([f"```json\n{LESSON_JSON}\n```"])
    _install_providers(monkeypatch, {"openai": primary})

    result = await generate_lesson(material_text="2 + 2 = 4")

    assert isinstance(result, LessonResult)


# ---------------------------------------------------------------------------
# Model-level validation
# ---------------------------------------------------------------------------


def test_quiz_question_requires_exactly_four_options() -> None:
    with pytest.raises(ValueError):
        QuizQuestion(
            question="Q?",
            options=["a", "b", "c"],
            correct_option_index=0,
        )


def test_quiz_question_rejects_out_of_range_index() -> None:
    with pytest.raises(ValueError):
        QuizQuestion(
            question="Q?",
            options=["a", "b", "c", "d"],
            correct_option_index=4,
        )


def test_evaluation_score_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValueError):
        EvaluationResult(
            is_correct=False,
            score=1.5,
            feedback="Too generous",
            next_step="Review",
        )


# ---------------------------------------------------------------------------
# Provider adapters (HTTP parsing and configuration)
# ---------------------------------------------------------------------------


async def test_openai_adapter_parses_chat_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(url: str, *, headers: dict, payload: dict, timeout: float) -> dict:
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer test-key"
        return {"choices": [{"message": {"content": LESSON_JSON}}]}

    monkeypatch.setattr(providers, "_post_json", fake_post)
    adapter = providers.OpenAIProvider(
        model="test-model", api_key="test-key", timeout=5, base_url=None
    )

    text = await adapter.generate(
        system_prompt="system",
        user_prompt="user",
        json_schema={"type": "object"},
        max_output_tokens=100,
        temperature=0.0,
    )

    assert text == LESSON_JSON


async def test_groq_adapter_uses_openai_compatible_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(url: str, *, headers: dict, payload: dict, timeout: float) -> dict:
        assert url == "https://api.groq.com/openai/v1/chat/completions"
        assert headers["Authorization"] == "Bearer test-key"
        assert payload["model"] == "llama-test"
        assert payload["reasoning_effort"] == "low"
        return {"choices": [{"message": {"content": LESSON_JSON}}]}

    monkeypatch.setattr(providers, "_post_json", fake_post)
    adapter = providers.GroqProvider(
        model="llama-test",
        api_key="test-key",
        timeout=5,
        base_url="https://api.groq.com/openai/v1",
        reasoning_effort="low",
    )

    text = await adapter.generate(
        system_prompt="system",
        user_prompt="user",
        json_schema={"type": "object"},
        max_output_tokens=100,
        temperature=0.0,
    )

    assert text == LESSON_JSON


async def test_groq_adapter_omits_reasoning_effort_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(url: str, *, headers: dict, payload: dict, timeout: float) -> dict:
        assert "reasoning_effort" not in payload
        return {"choices": [{"message": {"content": LESSON_JSON}}]}

    monkeypatch.setattr(providers, "_post_json", fake_post)
    adapter = providers.GroqProvider(
        model="llama-test",
        api_key="test-key",
        timeout=5,
        base_url="https://api.groq.com/openai/v1",
        reasoning_effort=None,
    )

    text = await adapter.generate(
        system_prompt="system",
        user_prompt="user",
        json_schema={"type": "object"},
        max_output_tokens=100,
        temperature=0.0,
    )

    assert text == LESSON_JSON


async def test_gemini_adapter_parses_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(url: str, *, headers: dict, payload: dict, timeout: float) -> dict:
        assert "generateContent" in url
        assert headers["x-goog-api-key"] == "test-key"
        return {
            "candidates": [
                {"content": {"parts": [{"text": LESSON_JSON}]}},
            ]
        }

    monkeypatch.setattr(providers, "_post_json", fake_post)
    adapter = providers.GeminiProvider(
        model="gemini-test",
        api_key="test-key",
        timeout=5,
        base_url="https://generativelanguage.googleapis.com/v1beta",
    )

    text = await adapter.generate(
        system_prompt="system",
        user_prompt="user",
        json_schema={"type": "object"},
        max_output_tokens=100,
        temperature=0.0,
    )

    assert text == LESSON_JSON


def test_build_provider_requires_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    with pytest.raises(providers.ProviderConfigurationError):
        providers.build_provider("openai", config=settings)


def test_configured_providers_reports_only_ready_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "configured")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    assert providers.configured_providers(settings) == ["groq"]


def test_anthropic_provider_was_removed() -> None:
    with pytest.raises(providers.ProviderConfigurationError, match="Unknown AI provider"):
        providers.build_provider("anthropic", config=settings)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = {"retry-after": "2"}

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *, response: _FakeResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


@pytest.mark.parametrize(
    ("status_code", "expected_type", "expected_transient"),
    [
        (429, providers.ProviderTransientError, True),
        (500, providers.ProviderTransientError, True),
        (401, providers.ProviderPermanentError, False),
        (400, providers.ProviderPermanentError, False),
    ],
)
async def test_http_status_classification(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_type: type[providers.ProviderCallError],
    expected_transient: bool,
) -> None:
    monkeypatch.setattr(
        providers.httpx,
        "AsyncClient",
        lambda timeout: _FakeAsyncClient(response=_FakeResponse(status_code)),
    )

    with pytest.raises(expected_type) as exc_info:
        await providers._post_json(
            "https://example.invalid",
            headers={},
            payload={},
            timeout=5,
        )

    assert exc_info.value.transient is expected_transient


async def test_transport_timeout_is_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        providers.httpx,
        "AsyncClient",
        lambda timeout: _FakeAsyncClient(error=providers.httpx.TimeoutException("timeout")),
    )

    with pytest.raises(providers.ProviderTransientError):
        await providers._post_json(
            "https://example.invalid",
            headers={},
            payload={},
            timeout=5,
        )
