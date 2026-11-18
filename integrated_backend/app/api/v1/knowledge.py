"""Knowledge Hub API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user_id
from app.schemas.knowledge import KnowledgeItemCreate, KnowledgeItemResponse
from app.services import knowledge_service

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge-hub"])


@router.get("", response_model=list[KnowledgeItemResponse])
def list_knowledge(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> list[KnowledgeItemResponse]:
    items = knowledge_service.list_knowledge_items(user_id, category, search)
    return [KnowledgeItemResponse(**it) for it in items]


@router.post("", response_model=KnowledgeItemResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_item(
    payload: KnowledgeItemCreate,
    user_id: str = Depends(get_current_user_id),
) -> KnowledgeItemResponse:
    item = knowledge_service.create_knowledge_item(user_id, payload.model_dump())
    return KnowledgeItemResponse(**item)


@router.get("/{item_id}", response_model=KnowledgeItemResponse)
def get_knowledge_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
) -> KnowledgeItemResponse:
    item = knowledge_service.get_knowledge_item(user_id, item_id)
    return KnowledgeItemResponse(**item)


@router.delete("/{item_id}")
def delete_knowledge_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    knowledge_service.delete_knowledge_item(user_id, item_id)
    return {"status": "success", "message": "Knowledge item deleted."}
