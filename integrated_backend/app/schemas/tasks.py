"""Pydantic schemas for Tasks, Projects, and Productivity Automation."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#6366f1", max_length=20)
    description: str = Field(default="", max_length=500)


class ProjectResponse(BaseModel):
    id: str
    name: str
    color: str
    description: str
    task_count: int = 0
    created_at: str | None = None


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2_000)
    due_at: str | None = Field(default=None, max_length=50)
    priority: str = Field(default="medium", pattern=r"^(urgent|high|medium|low)$")
    status: str = Field(default="todo", pattern=r"^(todo|in_progress|completed|blocked)$")
    project_id: str | None = None
    source_message_id: str | None = None
    confidence: float = 1.0


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=2_000)
    due_at: str | None = None
    priority: str | None = Field(default=None, pattern=r"^(urgent|high|medium|low)$")
    status: str | None = Field(default=None, pattern=r"^(todo|in_progress|completed|blocked)$")
    project_id: str | None = None


class TaskResponse(BaseModel):
    id: str
    project_id: str | None = None
    source_message_id: str | None = None
    title: str
    description: str
    due_at: str | None = None
    status: str
    priority: str
    confidence: float = 1.0
    created_at: str | None = None
    updated_at: str | None = None


class KanbanBoardResponse(BaseModel):
    todo: list[TaskResponse] = Field(default_factory=list)
    in_progress: list[TaskResponse] = Field(default_factory=list)
    completed: list[TaskResponse] = Field(default_factory=list)
    blocked: list[TaskResponse] = Field(default_factory=list)
    total_tasks: int = 0
    completed_today: int = 0


class ApproveTaskRequest(BaseModel):
    title: str
    description: str = ""
    due_at: str | None = None
    priority: str = "medium"
    source_message_id: str | None = None
    confidence: float = 0.9


class DailyBriefingResponse(BaseModel):
    date: str
    summary_greeting: str
    urgent_priorities: list[dict[str, Any]] = Field(default_factory=list)
    todays_tasks: list[TaskResponse] = Field(default_factory=list)
    todays_meetings: list[dict[str, Any]] = Field(default_factory=list)
    pending_follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    focus_advice: str = ""


class DeadlineRadarItem(BaseModel):
    id: str
    type: str  # task, email, event
    title: str
    due_date: str
    urgency: str
    source_title: str | None = None
