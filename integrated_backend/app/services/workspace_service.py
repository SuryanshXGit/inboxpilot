"""Persistence for the InboxPilot workspace document.

The SQL lives here so the route layer stays thin and the table is only touched
through one small, ownership-scoped code path.
"""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from app.db.client import get_db


def get_workspace_state(user_id: str) -> dict[str, Any] | None:
    """Return ``{"state": ..., "updated_at": ...}`` for one user, or ``None``."""

    with get_db() as cur:
        cur.execute(
            """
            SELECT state, updated_at
            FROM inboxpilot_workspaces
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    return row


def save_workspace_state(user_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Insert or replace the authenticated user's workspace document."""

    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO inboxpilot_workspaces (user_id, state, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET state = EXCLUDED.state,
                updated_at = NOW()
            RETURNING state, updated_at
            """,
            (user_id, Jsonb(state)),
        )
        row = cur.fetchone()
    return row or {"state": state, "updated_at": None}
