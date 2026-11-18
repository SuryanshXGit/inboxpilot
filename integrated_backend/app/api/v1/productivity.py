"""Productivity Intelligence API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.schemas.tasks import DailyBriefingResponse, DeadlineRadarItem
from app.services import productivity_service

router = APIRouter(prefix="/api/v1/productivity", tags=["productivity-intelligence"])


@router.get("/briefing", response_model=DailyBriefingResponse)
def get_daily_briefing(user_id: str = Depends(get_current_user_id)) -> DailyBriefingResponse:
    """Retrieve daily executive briefing combining priorities, tasks, and meetings."""
    data = productivity_service.get_daily_briefing(user_id)
    return DailyBriefingResponse(**data)


@router.get("/deadline-radar", response_model=list[DeadlineRadarItem])
def get_deadline_radar(user_id: str = Depends(get_current_user_id)) -> list[DeadlineRadarItem]:
    """Retrieve unified radar of approaching deadlines across emails, tasks, and calendar."""
    items = productivity_service.get_deadline_radar(user_id)
    return [DeadlineRadarItem(**it) for it in items]


@router.get("/waiting-for")
def get_waiting_for(user_id: str = Depends(get_current_user_id)) -> list[dict[str, Any]]:
    """Retrieve waiting-for list of sent items expecting a response."""
    return productivity_service.get_waiting_for(user_id)


@router.get("/focus")
def get_focus_mode(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """Retrieve focused high-priority workload for deep work mode."""
    return productivity_service.get_focus_mode(user_id)
