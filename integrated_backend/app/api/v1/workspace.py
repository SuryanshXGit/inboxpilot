"""API routes for the InboxPilot workspace.

Routes are additive: the existing learning API is untouched.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_user_id
from app.schemas.workspace import WorkspaceResponse, WorkspaceState
from app.services import workspace_service

router = APIRouter(prefix="/api/v1", tags=["inboxpilot"])


@router.get("/workspace", response_model=WorkspaceResponse)
def get_workspace(
    response: Response,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceResponse:
    """Return the current user's workspace, or an empty one on first use."""

    response.headers["Cache-Control"] = "no-store"
    row = workspace_service.get_workspace_state(user_id)
    if row is None:
        return WorkspaceResponse()
    return WorkspaceResponse.model_validate(
        {**row["state"], "updated_at": row["updated_at"]}
    )


@router.put("/workspace", response_model=WorkspaceResponse)
def save_workspace(
    payload: WorkspaceState,
    response: Response,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceResponse:
    """Replace the current user's workspace with the supplied document."""

    response.headers["Cache-Control"] = "no-store"
    saved = workspace_service.save_workspace_state(
        user_id,
        payload.model_dump(mode="python"),
    )
    return WorkspaceResponse.model_validate(
        {**saved["state"], "updated_at": saved["updated_at"]}
    )
