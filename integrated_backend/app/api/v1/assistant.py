"""AI Personal Assistant API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse
from app.services import assistant_service

router = APIRouter(prefix="/api/v1/assistant", tags=["ai-assistant"])


@router.post("/query", response_model=AssistantQueryResponse)
async def query_assistant(
    payload: AssistantQueryRequest,
    user_id: str = Depends(get_current_user_id),
) -> AssistantQueryResponse:
    """Send natural language question to context-aware personal assistant."""
    data = await assistant_service.answer_assistant_query(
        user_id=user_id,
        query=payload.query,
        include_emails=payload.include_emails,
        include_tasks=payload.include_tasks,
        include_calendar=payload.include_calendar,
    )
    return AssistantQueryResponse(**data)
