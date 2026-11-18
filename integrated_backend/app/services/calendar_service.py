"""Calendar and Meeting Intelligence Service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status

from app.db.client import get_db


def list_events(
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    where_clauses = ["user_id = %s"]
    params: list[Any] = [str(user_id)]

    if start_date:
        where_clauses.append("starts_at >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("starts_at <= %s")
        params.append(end_date)

    where_sql = " AND ".join(where_clauses)

    with get_db() as cur:
        # If no events exist for user, seed initial calendar schedule
        cur.execute("SELECT COUNT(*) as count FROM calendar_events WHERE user_id = %s", (str(user_id),))
        if cur.fetchone()["count"] == 0:
            _seed_initial_calendar(user_id)

        cur.execute(
            f"""
            SELECT id, title, description, location, starts_at, ends_at,
                   all_day, priority, source_message_id, created_at
            FROM calendar_events
            WHERE {where_sql}
            ORDER BY starts_at ASC
            """,
            tuple(params),
        )
        rows = cur.fetchall()

    return [_format_event(r) for r in rows]


def get_event(user_id: str, event_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, title, description, location, starts_at, ends_at,
                   all_day, priority, source_message_id, created_at
            FROM calendar_events
            WHERE user_id = %s AND id = %s
            """,
            (str(user_id), str(event_id)),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    return _format_event(row)


def create_event(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    event_id = str(uuid.uuid4())
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO calendar_events (
                id, user_id, title, description, location, starts_at, ends_at,
                all_day, priority, source_message_id, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                event_id, str(user_id), data["title"].strip(), data.get("description", "").strip(),
                data.get("location", "").strip(), data["starts_at"], data["ends_at"],
                data.get("all_day", False), data.get("priority", "medium"), data.get("source_message_id"),
            ),
        )
    return get_event(user_id, event_id)


def update_event(user_id: str, event_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = get_event(user_id, event_id)
    title = updates.get("title") if updates.get("title") is not None else current["title"]
    desc = updates.get("description") if updates.get("description") is not None else current["description"]
    loc = updates.get("location") if updates.get("location") is not None else current["location"]
    starts = updates.get("starts_at") if updates.get("starts_at") is not None else current["starts_at"]
    ends = updates.get("ends_at") if updates.get("ends_at") is not None else current["ends_at"]
    all_day = updates.get("all_day") if updates.get("all_day") is not None else current["all_day"]
    prio = updates.get("priority") if updates.get("priority") is not None else current["priority"]

    with get_db() as cur:
        cur.execute(
            """
            UPDATE calendar_events
            SET title = %s, description = %s, location = %s, starts_at = %s,
                ends_at = %s, all_day = %s, priority = %s, updated_at = NOW()
            WHERE user_id = %s AND id = %s
            """,
            (title, desc, loc, starts, ends, all_day, prio, str(user_id), str(event_id)),
        )
    return get_event(user_id, event_id)


def delete_event(user_id: str, event_id: str) -> None:
    with get_db() as cur:
        cur.execute(
            "DELETE FROM calendar_events WHERE user_id = %s AND id = %s",
            (str(user_id), str(event_id)),
        )


def _seed_initial_calendar(user_id: str) -> None:
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    events = [
        {"title": "Product Architecture Review", "desc": "Sprint sync with full-stack team", "loc": "Conference Room A", "starts": f"{today_iso} 10:30", "ends": f"{today_iso} 11:30", "prio": "high"},
        {"title": "NovaTech Syndicate Call", "desc": "Seed round investment discussion with Elena Rostova", "loc": "Zoom Video", "starts": f"{today_iso} 14:00", "ends": f"{today_iso} 14:45", "prio": "high"},
        {"title": "Venue Tech Walkthrough", "desc": "Seminar Hall projector and audio check with PEC AV staff", "loc": "Main Auditorium", "starts": f"{today_iso} 16:30", "ends": f"{today_iso} 17:15", "prio": "medium"},
    ]
    with get_db() as cur:
        for ev in events:
            cur.execute(
                """
                INSERT INTO calendar_events (id, user_id, title, description, location, starts_at, ends_at, all_day, priority, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, false, %s, NOW(), NOW())
                """,
                (str(uuid.uuid4()), str(user_id), ev["title"], ev["desc"], ev["loc"], ev["starts"], ev["ends"], ev["prio"]),
            )


def _format_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "description": str(row.get("description") or ""),
        "location": str(row.get("location") or ""),
        "starts_at": str(row["starts_at"]),
        "ends_at": str(row["ends_at"]),
        "all_day": bool(row.get("all_day")),
        "priority": str(row.get("priority") or "medium"),
        "source_message_id": str(row["source_message_id"]) if row.get("source_message_id") else None,
        "created_at": str(row.get("created_at") or ""),
    }
