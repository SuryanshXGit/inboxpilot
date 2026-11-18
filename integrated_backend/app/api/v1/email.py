"""Smart Inbox and Email Intelligence API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user_id
from app.schemas.email import (
    CategoryUpdateRequest,
    ConnectAccountRequest,
    ConnectedAccountResponse,
    EmailThreadListResponse,
    ReplyDraftRequest,
    ThreadDetailResponse,
)
from app.services import email_service

router = APIRouter(prefix="/api/v1/emails", tags=["smart-inbox"])


@router.get("/accounts", response_model=list[ConnectedAccountResponse])
def list_accounts(user_id: str = Depends(get_current_user_id)) -> list[ConnectedAccountResponse]:
    accounts = email_service.list_connected_accounts(user_id)
    return [ConnectedAccountResponse(**a) for a in accounts]


@router.post("/accounts", response_model=ConnectedAccountResponse, status_code=status.HTTP_201_CREATED)
def connect_account(
    payload: ConnectAccountRequest,
    user_id: str = Depends(get_current_user_id),
) -> ConnectedAccountResponse:
    account = email_service.connect_account(
        user_id,
        payload.provider,
        payload.email_address,
        payload.auth_code_or_token,
    )
    return ConnectedAccountResponse(**account)


@router.delete("/accounts/{account_id}")
def disconnect_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    email_service.disconnect_account(user_id, account_id)
    return {"status": "success", "message": "Account disconnected."}


@router.post("/accounts/{account_id}/sync")
def sync_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return email_service.sync_account_emails(user_id, account_id)


@router.get("/threads", response_model=EmailThreadListResponse)
def list_threads(
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    unread: bool = Query(default=False),
    starred: bool = Query(default=False),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> EmailThreadListResponse:
    data = email_service.get_threads(
        user_id=user_id,
        category=category,
        priority=priority,
        unread_only=unread,
        starred_only=starred,
        search=search,
        page=page,
        page_size=page_size,
    )
    return EmailThreadListResponse(**data)


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
def get_thread_detail(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
) -> ThreadDetailResponse:
    detail = email_service.get_thread_detail(user_id, thread_id)
    return ThreadDetailResponse(**detail)


@router.patch("/threads/{thread_id}/category")
def update_category(
    thread_id: str,
    payload: CategoryUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    thread = email_service.update_thread_category(user_id, thread_id, payload.category)
    return {"status": "success", "thread": thread}


@router.post("/threads/{thread_id}/star")
def toggle_star(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    thread = email_service.toggle_thread_star(user_id, thread_id)
    return {"status": "success", "thread": thread}


@router.post("/threads/{thread_id}/summarize")
async def summarize_thread(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Summarize an email conversation using AI with key points, decisions, and questions."""
    return await email_service.summarize_thread(user_id, thread_id)


@router.post("/threads/{thread_id}/reply-draft")
async def generate_reply_draft(
    thread_id: str,
    payload: ReplyDraftRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Generate contextual email reply draft in selected tone."""
    return await email_service.draft_thread_reply(
        user_id,
        thread_id,
        tone=payload.tone,
        user_notes=payload.user_notes,
    )


@router.post("/threads/{thread_id}/extract-tasks")
async def extract_tasks(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Extract action items, owners, and deadlines with confidence score."""
    return await email_service.extract_tasks_from_thread(user_id, thread_id)


@router.get("/messages/{message_id}/security")
async def check_message_security(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Analyze email security, phishing indicators, and spoofing risks."""
    return await email_service.analyze_message_security(user_id, message_id)
