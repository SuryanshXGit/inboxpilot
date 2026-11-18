"""Productivity Analytics API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.schemas.automation import AnalyticsOverviewResponse
from app.services import automation_service

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(user_id: str = Depends(get_current_user_id)) -> AnalyticsOverviewResponse:
    """Return real database productivity analytics and metrics."""
    data = automation_service.get_analytics_overview(user_id)
    return AnalyticsOverviewResponse(**data)
