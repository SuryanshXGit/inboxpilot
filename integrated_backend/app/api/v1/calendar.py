"""Calendar and Meeting Intelligence API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user_id
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarEventUpdate,
)
from app.services import calendar_service

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


@router.get("/events", response_model=list[CalendarEventResponse])
def list_events(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> list[CalendarEventResponse]:
    events = calendar_service.list_events(user_id, start, end)
    return [CalendarEventResponse(**e) for e in events]


@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: CalendarEventCreate,
    user_id: str = Depends(get_current_user_id),
) -> CalendarEventResponse:
    ev = calendar_service.create_event(user_id, payload.model_dump())
    return CalendarEventResponse(**ev)


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
def get_event(event_id: str, user_id: str = Depends(get_current_user_id)) -> CalendarEventResponse:
    ev = calendar_service.get_event(user_id, event_id)
    return CalendarEventResponse(**ev)


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
def update_event(
    event_id: str,
    payload: CalendarEventUpdate,
    user_id: str = Depends(get_current_user_id),
) -> CalendarEventResponse:
    ev = calendar_service.update_event(user_id, event_id, payload.model_dump(exclude_unset=True))
    return CalendarEventResponse(**ev)


@router.delete("/events/{event_id}")
def delete_event(event_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    calendar_service.delete_event(user_id, event_id)
    return {"status": "success", "message": "Event deleted."}
