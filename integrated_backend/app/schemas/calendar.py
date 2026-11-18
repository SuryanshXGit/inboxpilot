"""Pydantic schemas for Calendar and Meeting Intelligence."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CalendarEventCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2_000)
    location: str = Field(default="", max_length=300)
    starts_at: str
    ends_at: str
    all_day: bool = False
    priority: str = Field(default="medium", pattern=r"^(high|medium|low)$")
    source_message_id: str | None = None


class CalendarEventUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=2_000)
    location: str | None = Field(default=None, max_length=300)
    starts_at: str | None = None
    ends_at: str | None = None
    all_day: bool | None = None
    priority: str | None = Field(default=None, pattern=r"^(high|medium|low)$")


class CalendarEventResponse(BaseModel):
    id: str
    title: str
    description: str
    location: str
    starts_at: str
    ends_at: str
    all_day: bool = False
    priority: str
    source_message_id: str | None = None
    created_at: str | None = None


class CalendarViewResponse(BaseModel):
    view_type: str  # month, week, day, agenda
    events: list[CalendarEventResponse]
    events_count: int
