"""Visual Automation Studio API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, status

from app.core.security import get_current_user_id
from app.schemas.automation import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionResponse,
    WorkflowRunResponse,
)
from app.services import automation_service

router = APIRouter(prefix="/api/v1/automations", tags=["automation-studio"])


@router.get("/workflows", response_model=list[WorkflowDefinitionResponse])
def list_workflows(user_id: str = Depends(get_current_user_id)) -> list[WorkflowDefinitionResponse]:
    workflows = automation_service.list_workflows(user_id)
    return [WorkflowDefinitionResponse(**w) for w in workflows]


@router.post("/workflows", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowDefinitionCreate,
    user_id: str = Depends(get_current_user_id),
) -> WorkflowDefinitionResponse:
    wf = automation_service.create_workflow(user_id, payload.model_dump())
    return WorkflowDefinitionResponse(**wf)


@router.get("/workflows/{wf_id}", response_model=WorkflowDefinitionResponse)
def get_workflow(wf_id: str, user_id: str = Depends(get_current_user_id)) -> WorkflowDefinitionResponse:
    wf = automation_service.get_workflow(user_id, wf_id)
    return WorkflowDefinitionResponse(**wf)


@router.post("/workflows/{wf_id}/toggle", response_model=WorkflowDefinitionResponse)
def toggle_workflow(wf_id: str, user_id: str = Depends(get_current_user_id)) -> WorkflowDefinitionResponse:
    wf = automation_service.toggle_workflow(user_id, wf_id)
    return WorkflowDefinitionResponse(**wf)


@router.post("/workflows/{wf_id}/test")
def test_workflow(wf_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return automation_service.execute_workflow_test(user_id, wf_id)


@router.get("/runs", response_model=list[WorkflowRunResponse])
def list_runs(user_id: str = Depends(get_current_user_id)) -> list[WorkflowRunResponse]:
    runs = automation_service.list_workflow_runs(user_id)
    return [WorkflowRunResponse(**r) for r in runs]


@router.delete("/workflows/{wf_id}")
def delete_workflow(wf_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    automation_service.delete_workflow(user_id, wf_id)
    return {"status": "success", "message": "Workflow deleted."}
