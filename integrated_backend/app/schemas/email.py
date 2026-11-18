"""Pydantic schemas for the Smart Inbox and Email Intelligence."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ConnectedAccountResponse(BaseModel):
    id: str
    provider: str
    email_address: str
    status: str
    last_synced_at: str | None = None
    created_at: str | None = None


class EmailMessageResponse(BaseModel):
    id: str
    thread_id: str
    provider_message_id: str
    sender_name: str
    sender_email: str
    recipients: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    body_html: str = ""
    received_at: str
    is_phishing: bool = False
    phishing_indicators: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class EmailThreadResponse(BaseModel):
    id: str
    provider_thread_id: str
    subject: str
    snippet: str
    category: str
    priority: str
    priority_reason: str
    is_unread: bool
    is_starred: bool
    is_archived: bool
    latest_at: str
    messages: list[EmailMessageResponse] = Field(default_factory=list)


class EmailThreadListResponse(BaseModel):
    threads: list[EmailThreadResponse]
    total_count: int
    page: int
    page_size: int
    categories_breakdown: dict[str, int] = Field(default_factory=dict)
    unread_count: int = 0
    priority_count: int = 0


class ThreadDetailResponse(BaseModel):
    thread: EmailThreadResponse
    messages: list[EmailMessageResponse]


class CategoryUpdateRequest(BaseModel):
    category: str = Field(pattern=r"^(Primary|Work|Personal|Education|Finance|Promotions|Updates|Important|Spam/Suspicious)$")


class ReplyDraftRequest(BaseModel):
    tone: str = Field(default="professional")
    user_notes: str = ""


class ConnectAccountRequest(BaseModel):
    provider: str = Field(pattern=r"^(google|outlook|imap|demo)$")
    email_address: str
    auth_code_or_token: str | None = None
