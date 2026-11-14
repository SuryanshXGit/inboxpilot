"""Pydantic request / response models for the learning API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AuthTokenRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid email address is required")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class MaterialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    source_type: str = Field(min_length=1, max_length=50)
    text: str | None = None
    storage_path: str | None = None

    @field_validator("title", "source_type")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @model_validator(mode="after")
    def require_content(self) -> "MaterialCreate":
        if not (self.text and self.text.strip()) and not (
            self.storage_path and self.storage_path.strip()
        ):
            raise ValueError("Either 'text' or 'storage_path' must be provided")
        return self


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    source_type: str
    extracted_text: str
    created_at: datetime


class SessionCreate(BaseModel):
    material_id: UUID
    learning_goal: str | None = Field(default=None, max_length=1000)

    @field_validator("learning_goal")
    @classmethod
    def normalize_goal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SessionSummaryResponse(BaseModel):
    session_id: UUID
    status: str


class SessionNextRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=500)

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class LessonResponse(BaseModel):
    lesson: Any


class AnswerRequest(BaseModel):
    question_id: UUID
    answer: str = Field(min_length=1, max_length=20_000)

    @field_validator("answer")
    @classmethod
    def strip_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Answer must not be blank")
        return value


class QuizRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    difficulty: str = Field(default="medium", min_length=1, max_length=50)
    count: int = Field(default=5, ge=1, le=20)

    @field_validator("topic", "difficulty")
    @classmethod
    def strip_quiz_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value


class QuizResponse(BaseModel):
    topic: str
    difficulty: str
    questions: list[dict[str, Any]]


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    material_id: UUID
    status: str
    current_topic: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: str
    content: str
    created_at: datetime


class SessionDetailResponse(BaseModel):
    session: SessionResponse
    messages: list[MessageResponse]


class EvaluationResponse(BaseModel):
    is_correct: bool | None = None
    score: float
    feedback: str | None = None
    next_step: str | None = None

    model_config = ConfigDict(extra="allow")


class ProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    material_id: UUID
    topic: str
    mastery_score: float
    updated_at: datetime
