"""Pydantic schemas for the AI Personal Assistant."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AssistantQueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=1_000)
    include_emails: bool = True
    include_tasks: bool = True
    include_calendar: bool = True


class AssistantQueryResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    query: str
