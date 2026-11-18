"""Tasks, Projects, and Productivity Automation API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user_id
from app.schemas.tasks import (
    ApproveTaskRequest,
    DailyBriefingResponse,
    DeadlineRadarItem,
    KanbanBoardResponse,
    ProjectCreate,
    ProjectResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services import productivity_service, task_service

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Tasks CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> list[TaskResponse]:
    tasks = task_service.list_tasks(
        user_id=user_id,
        status_filter=status,
        priority_filter=priority,
        project_id=project_id,
        search=search,
    )
    return [TaskResponse(**t) for t in tasks]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user_id: str = Depends(get_current_user_id),
) -> TaskResponse:
    task = task_service.create_task(user_id, payload.model_dump())
    return TaskResponse(**task)


@router.get("/kanban", response_model=KanbanBoardResponse)
def get_kanban_board(user_id: str = Depends(get_current_user_id)) -> KanbanBoardResponse:
    board = task_service.get_kanban_board(user_id)
    return KanbanBoardResponse(**board)


@router.post("/approve-extracted", response_model=TaskResponse)
def approve_extracted_task(
    payload: ApproveTaskRequest,
    user_id: str = Depends(get_current_user_id),
) -> TaskResponse:
    """Create a verified task in the database following human review and approval."""
    task = task_service.create_task(user_id, payload.model_dump())
    return TaskResponse(**task)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, user_id: str = Depends(get_current_user_id)) -> TaskResponse:
    task = task_service.get_task(user_id, task_id)
    return TaskResponse(**task)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    user_id: str = Depends(get_current_user_id),
) -> TaskResponse:
    task = task_service.update_task(user_id, task_id, payload.model_dump(exclude_unset=True))
    return TaskResponse(**task)


@router.delete("/{task_id}")
def delete_task(task_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    task_service.delete_task(user_id, task_id)
    return {"status": "success", "message": "Task deleted."}


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@router.get("/projects/all", response_model=list[ProjectResponse])
def list_projects(user_id: str = Depends(get_current_user_id)) -> list[ProjectResponse]:
    projects = task_service.list_projects(user_id)
    return [ProjectResponse(**p) for p in projects]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user_id: str = Depends(get_current_user_id),
) -> ProjectResponse:
    proj = task_service.create_project(user_id, payload.name, payload.color, payload.description)
    return ProjectResponse(**proj)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    task_service.delete_project(user_id, project_id)
    return {"status": "success", "message": "Project deleted."}
