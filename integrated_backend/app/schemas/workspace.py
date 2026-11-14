"""Pydantic models for the InboxPilot workspace state.

The frontend keeps a single workspace document (tasks, events, inbox messages,
notes and an approval flag). Storing it as one validated document keeps the
sync contract small and lets the browser stay usable offline. Unknown fields
are preserved so the frontend can add UI-only properties without a backend
change.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _required_text(value: str) -> str:
    """Trim a required string and reject values that are only whitespace."""

    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


def _iso_date(value: str) -> str:
    """Accept only real calendar dates written as ``YYYY-MM-DD``."""

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("must be a real date in YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise ValueError("must be a real date in YYYY-MM-DD format")
    return value


class _Item(BaseModel):
    model_config = ConfigDict(extra="allow")


class TaskItem(_Item):
    text: str = Field(min_length=1, max_length=500)
    due: str = Field(default="", max_length=500)
    done: bool = False

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _required_text(value)


class EventItem(_Item):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    name: str = Field(min_length=1, max_length=500)
    time: str = Field(default="", max_length=20)
    place: str = Field(default="", max_length=500)
    priority: Literal["high", "medium", "low"] = "medium"

    @field_validator("date")
    @classmethod
    def _validate_date(cls, value: str) -> str:
        return _iso_date(value)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _required_text(value)



class InboxMessageItem(_Item):
    name: str = Field(min_length=1, max_length=200)
    initial: str = Field(default="", max_length=8)
    subject: str = Field(default="", max_length=500)
    preview: str = Field(default="", max_length=2_000)
    priority: str = Field(default="MEDIUM", max_length=20)
    body: str = Field(default="", max_length=20_000)
    when: str | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _required_text(value)


class NoteItem(_Item):
    title: str = Field(min_length=1, max_length=500)
    details: str = Field(default="", max_length=2_000)
    body: str = Field(default="", max_length=20_000)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _required_text(value)



class WorkspaceState(BaseModel):
    """The mutable workspace document owned by one user."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[TaskItem] = Field(default_factory=list, max_length=500)
    events: list[EventItem] = Field(default_factory=list, max_length=1_000)
    messages: list[InboxMessageItem] = Field(default_factory=list, max_length=500)
    notes: list[NoteItem] = Field(default_factory=list, max_length=500)
    approval_state: Literal["pending", "approved", "rejected"] = "pending"


class WorkspaceResponse(WorkspaceState):
    """Workspace state plus the server-side modification time.

    ``updated_at`` is ``None`` until the user saves for the first time, which
    lets the frontend distinguish "no remote copy yet" from an empty workspace.
    """

    updated_at: datetime | None = None
