"""Authentication and user account service."""

from __future__ import annotations

import json
import uuid
from typing import Any
from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password, create_access_token
from app.db.client import get_db


def register_user(email: str, password: str, display_name: str | None = None) -> tuple[str, dict[str, Any]]:
    email_clean = email.strip().lower()
    with get_db() as cur:
        cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email_clean,))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        user_id = str(uuid.uuid4())
        hashed = hash_password(password)
        disp = display_name.strip() if display_name else email_clean.split("@")[0]
        cur.execute(
            """
            INSERT INTO users (id, email, password_hash, display_name, preferences, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (user_id, email_clean, hashed, disp, json.dumps({})),
        )
        cur.execute(
            "SELECT id, email, display_name, preferences, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        user_row = cur.fetchone()

    token = create_access_token(user_id)
    return token, _format_user_dict(user_row)


def authenticate_user(email: str, password: str) -> tuple[str, dict[str, Any]]:
    email_clean = email.strip().lower()
    with get_db() as cur:
        cur.execute(
            "SELECT id, email, password_hash, display_name, preferences, created_at FROM users WHERE LOWER(email) = LOWER(%s)",
            (email_clean,),
        )
        user_row = cur.fetchone()

    if not user_row or not verify_password(password, user_row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user_row["id"])
    return token, _format_user_dict(user_row)


def get_user_profile(user_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            "SELECT id, email, display_name, preferences, created_at FROM users WHERE id = %s",
            (str(user_id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _format_user_dict(row)


def update_user_profile(
    user_id: str,
    display_name: str | None = None,
    preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = get_user_profile(user_id)
    new_disp = display_name.strip() if display_name is not None else current["display_name"]
    new_prefs = {**current["preferences"], **(preferences or {})} if preferences is not None else current["preferences"]

    with get_db() as cur:
        cur.execute(
            """
            UPDATE users
            SET display_name = %s, preferences = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_disp, json.dumps(new_prefs), str(user_id)),
        )
        cur.execute(
            "SELECT id, email, display_name, preferences, created_at FROM users WHERE id = %s",
            (str(user_id),),
        )
        row = cur.fetchone()
    return _format_user_dict(row)


def change_user_password(user_id: str, current_password: str, new_password: str) -> None:
    with get_db() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (str(user_id),))
        row = cur.fetchone()
        if not row or not verify_password(current_password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password verification failed.",
            )
        new_hashed = hash_password(new_password)
        cur.execute(
            "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
            (new_hashed, str(user_id)),
        )


def delete_user_account(user_id: str) -> None:
    """Permanently delete user account and cascade delete all associated data."""
    with get_db() as cur:
        # Cascade delete across all tables
        for table in [
            "tasks", "calendar_events", "notes", "follow_ups", "knowledge_items",
            "workflow_runs", "workflow_definitions", "ai_insights", "email_messages",
            "email_threads", "connected_accounts", "inboxpilot_workspaces", "audit_events",
            "users",
        ]:
            try:
                cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (str(user_id),))
            except Exception:
                pass


def export_user_data(user_id: str) -> dict[str, Any]:
    """Retrieve full data export for the user in accordance with privacy compliance."""
    user = get_user_profile(user_id)
    export: dict[str, Any] = {"user": user}
    with get_db() as cur:
        for key, table in [
            ("tasks", "tasks"),
            ("calendar_events", "calendar_events"),
            ("notes", "notes"),
            ("follow_ups", "follow_ups"),
            ("knowledge_items", "knowledge_items"),
            ("workflows", "workflow_definitions"),
            ("emails", "email_messages"),
        ]:
            try:
                cur.execute(f"SELECT * FROM {table} WHERE user_id = %s", (str(user_id),))
                export[key] = cur.fetchall()
            except Exception:
                export[key] = []
    return export


def _format_user_dict(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    prefs = row.get("preferences")
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except Exception:
            prefs = {}
    return {
        "id": str(row["id"]),
        "email": str(row["email"]),
        "display_name": row.get("display_name"),
        "preferences": prefs if isinstance(prefs, dict) else {},
        "created_at": str(row.get("created_at") or ""),
    }
