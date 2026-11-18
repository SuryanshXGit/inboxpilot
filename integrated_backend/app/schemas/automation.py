"""Pydantic schemas for Automation Studio and Analytics."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class WorkflowDefinitionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    trigger_type: str = Field(pattern=r"^(email_received|priority_high|deadline_approaching|task_overdue|follow_up_due)$")
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    is_active: bool = True
    requires_approval: bool = False


class WorkflowDefinitionResponse(BaseModel):
    id: str
    name: str
    trigger_type: str
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    is_active: bool
    requires_approval: bool
    created_at: str | None = None
    runs_count: int = 0


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    trigger_event: dict[str, Any] = Field(default_factory=dict)
    status: str
    result_summary: str
    started_at: str
    completed_at: str | None = None


class AnalyticsOverviewResponse(BaseModel):
    emails_processed: int
    high_priority_count: int
    tasks_total: int
    tasks_completed: int
    tasks_overdue: int
    upcoming_deadlines: int
    pending_follow_ups: int
    categories_breakdown: dict[str, int] = Field(default_factory=dict)
    weekly_trend: list[dict[str, Any]] = Field(default_factory=list)
    time_saved_hours: float = 0.0
