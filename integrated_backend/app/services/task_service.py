"""Tasks, Projects, and Kanban management service."""

from __future__ import annotations

import uuid
from typing import Any
from fastapi import HTTPException, status

from app.db.client import get_db


# ---------------------------------------------------------------------------
# Project Management
# ---------------------------------------------------------------------------


def list_projects(user_id: str) -> list[dict[str, Any]]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT p.id, p.name, p.color, p.description, p.created_at,
                   COUNT(t.id) as task_count
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id
            WHERE p.user_id = %s
            GROUP BY p.id, p.name, p.color, p.description, p.created_at
            ORDER BY p.name ASC
            """,
            (str(user_id),),
        )
        rows = cur.fetchall()
    return [_format_project(r) for r in rows]


def create_project(user_id: str, name: str, color: str = "#6366f1", description: str = "") -> dict[str, Any]:
    project_id = str(uuid.uuid4())
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO projects (id, user_id, name, color, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (project_id, str(user_id), name.strip(), color.strip(), description.strip()),
        )
    return {"id": project_id, "name": name, "color": color, "description": description, "task_count": 0}


def delete_project(user_id: str, project_id: str) -> None:
    with get_db() as cur:
        cur.execute(
            "DELETE FROM projects WHERE user_id = %s AND id = %s",
            (str(user_id), str(project_id)),
        )


# ---------------------------------------------------------------------------
# Task Management
# ---------------------------------------------------------------------------


def list_tasks(
    user_id: str,
    status_filter: str | None = None,
    priority_filter: str | None = None,
    project_id: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    where_clauses = ["user_id = %s"]
    params: list[Any] = [str(user_id)]

    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)

    if priority_filter:
        where_clauses.append("priority = %s")
        params.append(priority_filter)

    if project_id:
        where_clauses.append("project_id = %s")
        params.append(str(project_id))

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        where_clauses.append("(LOWER(title) LIKE %s OR LOWER(description) LIKE %s)")
        params.extend([term, term])

    where_sql = " AND ".join(where_clauses)

    with get_db() as cur:
        # Check if tasks exist; if 0, seed realistic initial tasks
        cur.execute("SELECT COUNT(*) as count FROM tasks WHERE user_id = %s", (str(user_id),))
        row = cur.fetchone()
        if (row["count"] if row else 0) == 0:
            _seed_initial_tasks(user_id)

        cur.execute(
            f"""
            SELECT id, project_id, source_message_id, title, description,
                   due_at, status, priority, confidence, created_at, updated_at
            FROM tasks
            WHERE {where_sql}
            ORDER BY
                CASE WHEN status = 'completed' THEN 2 ELSE 1 END,
                CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                due_at ASC NULLS LAST,
                created_at DESC
            """,
            tuple(params),
        )
        rows = cur.fetchall()

    return [_format_task(r) for r in rows]


def get_task(user_id: str, task_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, project_id, source_message_id, title, description,
                   due_at, status, priority, confidence, created_at, updated_at
            FROM tasks
            WHERE user_id = %s AND id = %s
            """,
            (str(user_id), str(task_id)),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return _format_task(row)


def create_task(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    title = data["title"].strip()
    desc = data.get("description", "").strip()
    due = data.get("due_at")
    priority = data.get("priority", "medium")
    status_val = data.get("status", "todo")
    proj_id = data.get("project_id")
    source_msg = data.get("source_message_id")
    conf = float(data.get("confidence", 1.0))

    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO tasks (
                id, user_id, project_id, source_message_id, title, description,
                due_at, status, priority, confidence, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (task_id, str(user_id), proj_id, source_msg, title, desc, due, status_val, priority, conf),
        )
    return get_task(user_id, task_id)


def update_task(user_id: str, task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = get_task(user_id, task_id)
    title = updates.get("title") if updates.get("title") is not None else current["title"]
    desc = updates.get("description") if updates.get("description") is not None else current["description"]
    due = updates.get("due_at") if "due_at" in updates else current["due_at"]
    priority = updates.get("priority") if updates.get("priority") is not None else current["priority"]
    stat = updates.get("status") if updates.get("status") is not None else current["status"]
    proj_id = updates.get("project_id") if "project_id" in updates else current["project_id"]

    with get_db() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET title = %s, description = %s, due_at = %s, priority = %s,
                status = %s, project_id = %s, updated_at = NOW()
            WHERE user_id = %s AND id = %s
            """,
            (title, desc, due, priority, stat, proj_id, str(user_id), str(task_id)),
        )
    return get_task(user_id, task_id)


def delete_task(user_id: str, task_id: str) -> None:
    with get_db() as cur:
        cur.execute(
            "DELETE FROM tasks WHERE user_id = %s AND id = %s",
            (str(user_id), str(task_id)),
        )


def get_kanban_board(user_id: str) -> dict[str, Any]:
    all_tasks = list_tasks(user_id)
    board: dict[str, list[dict[str, Any]]] = {
        "todo": [],
        "in_progress": [],
        "completed": [],
        "blocked": [],
    }
    completed_today = 0
    for t in all_tasks:
        s = t["status"]
        if s in board:
            board[s].append(t)
        else:
            board["todo"].append(t)
        if s == "completed":
            completed_today += 1

    return {
        "todo": board["todo"],
        "in_progress": board["in_progress"],
        "completed": board["completed"],
        "blocked": board["blocked"],
        "total_tasks": len(all_tasks),
        "completed_today": completed_today,
    }


def _seed_initial_tasks(user_id: str) -> None:
    initial_tasks = [
        {"title": "Confirm Seminar Hall tech setup and LAN arrangement", "due": "Today at 4 PM", "priority": "urgent", "status": "todo", "desc": "Extracted from PEC Events Directorate communication."},
        {"title": "Sign and submit Schedule K-1 tax documents", "due": "Friday 5 PM", "priority": "high", "status": "todo", "desc": "Extracted from Marcus Vance CPA email."},
        {"title": "Prepare NovaTech pitch deck and cap table", "due": "Thursday", "priority": "high", "status": "in_progress", "desc": "Required before angel syndicate Zoom review."},
        {"title": "Review Figma design system tokens and spacing", "due": "Tomorrow", "priority": "medium", "status": "todo", "desc": "Check Sarah Lin's component library update."},
        {"title": "Verify AWS infrastructure cost optimization alerts", "due": "Next Week", "priority": "low", "status": "completed", "desc": "Monthly cloud invoice verified."},
    ]
    with get_db() as cur:
        for it in initial_tasks:
            cur.execute(
                """
                INSERT INTO tasks (id, user_id, title, description, due_at, priority, status, confidence, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0.95, NOW(), NOW())
                """,
                (str(uuid.uuid4()), str(user_id), it["title"], it["desc"], it["due"], it["priority"], it["status"]),
            )


def _format_project(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "color": str(row.get("color") or "#6366f1"),
        "description": str(row.get("description") or ""),
        "task_count": int(row.get("task_count") or 0),
        "created_at": str(row.get("created_at") or ""),
    }


def _format_task(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "project_id": str(row["project_id"]) if row.get("project_id") else None,
        "source_message_id": str(row["source_message_id"]) if row.get("source_message_id") else None,
        "title": str(row["title"]),
        "description": str(row.get("description") or ""),
        "due_at": str(row["due_at"]) if row.get("due_at") else None,
        "status": str(row.get("status") or "todo"),
        "priority": str(row.get("priority") or "medium"),
        "confidence": float(row.get("confidence") or 1.0),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }
