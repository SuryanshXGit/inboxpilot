"""Follow-ups Management API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user_id
from app.schemas.knowledge import FollowUpCreate, FollowUpResponse, FollowUpUpdate
from app.services import knowledge_service

router = APIRouter(prefix="/api/v1/follow-ups", tags=["follow-ups"])


@router.get("", response_model=list[FollowUpResponse])
def list_follow_ups(
    status: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> list[FollowUpResponse]:
    items = knowledge_service.list_follow_ups(user_id, status)
    return [FollowUpResponse(**it) for it in items]


@router.post("", response_model=FollowUpResponse, status_code=status.HTTP_201_CREATED)
def create_follow_up(
    payload: FollowUpCreate,
    user_id: str = Depends(get_current_user_id),
) -> FollowUpResponse:
    item = knowledge_service.create_follow_up(user_id, payload.model_dump())
    return FollowUpResponse(**item)


@router.get("/{fu_id}", response_model=FollowUpResponse)
def get_follow_up(fu_id: str, user_id: str = Depends(get_current_user_id)) -> FollowUpResponse:
    item = knowledge_service.get_follow_up(user_id, fu_id)
    return FollowUpResponse(**item)


@router.patch("/{fu_id}", response_model=FollowUpResponse)
def update_follow_up(
    fu_id: str,
    payload: FollowUpUpdate,
    user_id: str = Depends(get_current_user_id),
) -> FollowUpResponse:
    item = knowledge_service.update_follow_up(user_id, fu_id, payload.model_dump(exclude_unset=True))
    return FollowUpResponse(**item)


@router.delete("/{fu_id}")
def delete_follow_up(fu_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    knowledge_service.delete_follow_up(user_id, fu_id)
    return {"status": "success", "message": "Follow-up deleted."}
