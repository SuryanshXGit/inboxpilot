"""Pydantic schemas for Knowledge Hub and Follow-ups."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeItemCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=20_000)
    category: str = Field(default="general", max_length=100)
    tags: list[str] = Field(default_factory=list)
    source_type: str = Field(default="manual", pattern=r"^(email|attachment|note|task|manual)$")
    source_id: str = ""


class KnowledgeItemResponse(BaseModel):
    id: str
    title: str
    content: str
    category: str
    tags: list[str] = Field(default_factory=list)
    source_type: str
    source_id: str
    created_at: str | None = None
    updated_at: str | None = None


class FollowUpCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recipient: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=300)
    expected_by: str = Field(min_length=1, max_length=50)
    suggested_action: str = ""
    thread_id: str | None = None


class FollowUpUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(pending|replied|snoozed|dismissed)$")
    expected_by: str | None = None
    draft_reply: str | None = None


class FollowUpResponse(BaseModel):
    id: str
    thread_id: str | None = None
    recipient: str
    subject: str
    last_sent_at: str
    expected_by: str
    status: str
    suggested_action: str
    draft_reply: str = ""
    created_at: str | None = None
