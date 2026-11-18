"""Authentication and user management API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, status

from app.core.security import get_current_user_id
from app.schemas.auth import (
    AuthTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UpdateProfileRequest,
    UserProfileResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> AuthTokenResponse:
    """Create a new user account and return signed JWT."""
    token, user = auth_service.register_user(
        payload.email,
        payload.password,
        payload.display_name,
    )
    return AuthTokenResponse(access_token=token, user=UserProfileResponse(**user))


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest) -> AuthTokenResponse:
    """Authenticate with email and password and return signed JWT."""
    token, user = auth_service.authenticate_user(payload.email, payload.password)
    return AuthTokenResponse(access_token=token, user=UserProfileResponse(**user))


@router.post("/logout", response_model=MessageResponse)
def logout(user_id: str = Depends(get_current_user_id)) -> MessageResponse:
    """Logout current user (client invalidates stored token)."""
    return MessageResponse(message="Successfully logged out.")


@router.get("/me", response_model=UserProfileResponse)
def get_current_profile(user_id: str = Depends(get_current_user_id)) -> UserProfileResponse:
    """Return the currently authenticated user's profile and preferences."""
    user = auth_service.get_user_profile(user_id)
    return UserProfileResponse(**user)


@router.put("/profile", response_model=UserProfileResponse)
def update_profile(
    payload: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
) -> UserProfileResponse:
    """Update display name and user preferences."""
    user = auth_service.update_user_profile(
        user_id,
        display_name=payload.display_name,
        preferences=payload.preferences,
    )
    return UserProfileResponse(**user)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
) -> MessageResponse:
    """Change account password after verifying current password."""
    auth_service.change_user_password(user_id, payload.current_password, payload.new_password)
    return MessageResponse(message="Password successfully updated.")


@router.get("/export")
def export_data(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """Export complete user data for GDPR/privacy compliance."""
    return auth_service.export_user_data(user_id)


@router.delete("/me", response_model=MessageResponse)
def delete_account(user_id: str = Depends(get_current_user_id)) -> MessageResponse:
    """Permanently delete user account and all associated emails, tasks, and data."""
    auth_service.delete_user_account(user_id)
    return MessageResponse(message="Account and all personal data permanently deleted.")
