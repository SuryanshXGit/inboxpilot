"""Pydantic contracts for every structured AI response.

Person 1's persistence layer stores these structures as JSON, so the field
names in this module are part of the shared API/database contract. Keep them
stable; add optional fields instead of renaming existing ones.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class AIEngineError(RuntimeError):
    """Base class for errors that callers may translate into an HTTP response."""


class AIProviderUnavailable(AIEngineError):
    """No configured AI provider could serve the request."""


class AIOutputInvalid(AIEngineError):
    """A provider responded, but the payload failed schema validation."""


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class LessonResult(BaseModel):
    """A single, self-contained lesson generated from the supplied material."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=30_000)
    key_points: list[str] = Field(min_length=1, max_length=20)
    examples: list[str] = Field(default_factory=list, max_length=20)
    check_for_understanding: str = Field(min_length=1, max_length=4_000)
    suggested_next_topic: str = Field(min_length=1, max_length=300)

    @field_validator("title", "explanation", "check_for_understanding", "suggested_next_topic")
    @classmethod
    def _require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("key_points", "examples")
    @classmethod
    def _clean_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    @model_validator(mode="after")
    def _require_key_points(self) -> "LessonResult":
        if not self.key_points:
            raise ValueError("key_points must contain at least one non-empty item")
        return self


class QuizQuestion(BaseModel):
    """One multiple-choice question with exactly four options."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=4_000)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option_index: int = Field(ge=0, le=3)
    explanation: str = Field(default="", max_length=4_000)
    difficulty: str = Field(default="medium", min_length=1, max_length=50)

    @field_validator("question")
    @classmethod
    def _require_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value

    @field_validator("options")
    @classmethod
    def _validate_options(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if len(cleaned) != 4:
            raise ValueError("exactly four options are required")
        if any(not item for item in cleaned):
            raise ValueError("options must not be blank")
        if len({item.casefold() for item in cleaned}) != 4:
            raise ValueError("options must be unique")
        return cleaned

    @field_validator("difficulty")
    @classmethod
    def _normalise_difficulty(cls, value: str) -> str:
        value = value.strip().lower()
        return value or "medium"

    @model_validator(mode="after")
    def _explanation_fallback(self) -> "QuizQuestion":
        if not self.explanation:
            self.explanation = f"The correct option is {self.options[self.correct_option_index]}."
        return self


class QuizResult(BaseModel):
    """A generated quiz for one topic."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    topic: str = Field(min_length=1, max_length=500)
    questions: list[QuizQuestion] = Field(min_length=1, max_length=20)

    @field_validator("topic")
    @classmethod
    def _require_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must not be blank")
        return value


class EvaluationResult(BaseModel):
    """Assessment of one student answer."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(min_length=1, max_length=8_000)
    misconception: str | None = Field(default=None, max_length=4_000)
    next_step: str = Field(min_length=1, max_length=2_000)

    @field_validator("feedback", "next_step")
    @classmethod
    def _require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("misconception")
    @classmethod
    def _normalise_misconception(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


# ---------------------------------------------------------------------------
# Helpers used by the workflow and the API adapter
# ---------------------------------------------------------------------------


TASK_MODELS: dict[str, type[BaseModel]] = {
    "lesson": LessonResult,
    "quiz": QuizResult,
    "evaluation": EvaluationResult,
}


def model_payload(value: Any) -> Any:
    """Return a JSON-compatible payload for a model or a legacy value.

    The original AI boundary returned plain ``str`` / ``list`` / ``dict``
    objects. Keeping this helper tolerant lets the service layer accept both
    the typed engine output and older/mocked implementations.
    """

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value
