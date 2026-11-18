"""Knowledge Hub and Follow-up Management services."""

from __future__ import annotations

import json
import uuid
from typing import Any
from fastapi import HTTPException, status

from app.db.client import get_db


# ---------------------------------------------------------------------------
# Knowledge Hub Service
# ---------------------------------------------------------------------------


def list_knowledge_items(
    user_id: str,
    category: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    where_clauses = ["user_id = %s"]
    params: list[Any] = [str(user_id)]

    if category and category.lower() != "all":
        where_clauses.append("category = %s")
        params.append(category)

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        where_clauses.append("(LOWER(title) LIKE %s OR LOWER(content) LIKE %s)")
        params.extend([term, term])

    where_sql = " AND ".join(where_clauses)

    with get_db() as cur:
        # If empty, seed initial knowledge items
        cur.execute("SELECT COUNT(*) as count FROM knowledge_items WHERE user_id = %s", (str(user_id),))
        if cur.fetchone()["count"] == 0:
            _seed_knowledge_items(user_id)

        cur.execute(
            f"""
            SELECT id, title, content, category, tags, source_type, source_id, created_at, updated_at
            FROM knowledge_items
            WHERE {where_sql}
            ORDER BY created_at DESC
            """,
            tuple(params),
        )
        rows = cur.fetchall()

    return [_format_knowledge(r) for r in rows]


def create_knowledge_item(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    item_id = str(uuid.uuid4())
    tags = data.get("tags", [])
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_items (id, user_id, title, content, category, tags, source_type, source_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                item_id, str(user_id), data["title"].strip(), data["content"].strip(),
                data.get("category", "general").strip(), json.dumps(tags),
                data.get("source_type", "manual"), data.get("source_id", ""),
            ),
        )
    return get_knowledge_item(user_id, item_id)


def get_knowledge_item(user_id: str, item_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, title, content, category, tags, source_type, source_id, created_at, updated_at
            FROM knowledge_items
            WHERE user_id = %s AND id = %s
            """,
            (str(user_id), str(item_id)),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found.")
    return _format_knowledge(row)


def delete_knowledge_item(user_id: str, item_id: str) -> None:
    with get_db() as cur:
        cur.execute("DELETE FROM knowledge_items WHERE user_id = %s AND id = %s", (str(user_id), str(item_id)))


def _seed_knowledge_items(user_id: str) -> None:
    seeds = [
        {
            "title": "Corporate Tax & Filing Schedule K-1 Requirements",
            "content": "Signed Schedule K-1 and quarterly expense reports must be delivered to Marcus Vance CPA prior to Nov 20 for annual tax compliance.",
            "cat": "Finance",
            "tags": ["taxes", "compliance", "vance-cpa"],
            "source_type": "email",
        },
        {
            "title": "Seminar Hall AV & High-Speed LAN Configuration",
            "content": "Audiovisual equipment and high-speed network drop for the AI Showcase must be confirmed with the Student Activities Dean before 4 PM on day of setup.",
            "cat": "Events",
            "tags": ["pec", "venue", "logistics"],
            "source_type": "email",
        },
        {
            "title": "NovaTech Ventures Investment Terms & Seed Round Scope",
            "content": "Angel syndicate interested in participating in the seed round. Requires updated cap table and 2027 product roadmap prior to Thursday review call.",
            "cat": "Fundraising",
            "tags": ["investors", "seed", "novatech"],
            "source_type": "email",
        },
    ]
    with get_db() as cur:
        for s in seeds:
            cur.execute(
                """
                INSERT INTO knowledge_items (id, user_id, title, content, category, tags, source_type, source_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, '', NOW(), NOW())
                """,
                (str(uuid.uuid4()), str(user_id), s["title"], s["content"], s["cat"], json.dumps(s["tags"]), s["source_type"]),
            )


# ---------------------------------------------------------------------------
# Follow-up Service
# ---------------------------------------------------------------------------


def list_follow_ups(user_id: str, status_filter: str | None = None) -> list[dict[str, Any]]:
    where_clauses = ["user_id = %s"]
    params: list[Any] = [str(user_id)]
    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)

    where_sql = " AND ".join(where_clauses)
    with get_db() as cur:
        cur.execute(
            f"""
            SELECT id, thread_id, recipient, subject, last_sent_at, expected_by,
                   status, suggested_action, draft_reply, created_at
            FROM follow_ups
            WHERE {where_sql}
            ORDER BY expected_by ASC
            """,
            tuple(params),
        )
        rows = cur.fetchall()
    return [_format_follow_up(r) for r in rows]


def create_follow_up(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    fu_id = str(uuid.uuid4())
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO follow_ups (
                id, user_id, thread_id, recipient, subject, expected_by,
                status, suggested_action, draft_reply, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, '', NOW(), NOW())
            """,
            (
                fu_id, str(user_id), data.get("thread_id"), data["recipient"].strip(),
                data["subject"].strip(), data["expected_by"].strip(),
                data.get("suggested_action", ""),
            ),
        )
    return get_follow_up(user_id, fu_id)


def get_follow_up(user_id: str, fu_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, thread_id, recipient, subject, last_sent_at, expected_by,
                   status, suggested_action, draft_reply, created_at
            FROM follow_ups
            WHERE user_id = %s AND id = %s
            """,
            (str(user_id), str(fu_id)),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return _format_follow_up(row)


def update_follow_up(user_id: str, fu_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = get_follow_up(user_id, fu_id)
    new_status = updates.get("status") or current["status"]
    new_exp = updates.get("expected_by") or current["expected_by"]
    draft = updates.get("draft_reply") if "draft_reply" in updates else current["draft_reply"]

    with get_db() as cur:
        cur.execute(
            """
            UPDATE follow_ups
            SET status = %s, expected_by = %s, draft_reply = %s, updated_at = NOW()
            WHERE user_id = %s AND id = %s
            """,
            (new_status, new_exp, draft, str(user_id), str(fu_id)),
        )
    return get_follow_up(user_id, fu_id)


def delete_follow_up(user_id: str, fu_id: str) -> None:
    with get_db() as cur:
        cur.execute("DELETE FROM follow_ups WHERE user_id = %s AND id = %s", (str(user_id), str(fu_id)))


def _format_knowledge(row: dict[str, Any]) -> dict[str, Any]:
    tags = row.get("tags")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "category": str(row.get("category") or "general"),
        "tags": tags if isinstance(tags, list) else [],
        "source_type": str(row.get("source_type") or "manual"),
        "source_id": str(row.get("source_id") or ""),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def _format_follow_up(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "thread_id": str(row["thread_id"]) if row.get("thread_id") else None,
        "recipient": str(row["recipient"]),
        "subject": str(row["subject"]),
        "last_sent_at": str(row.get("last_sent_at") or ""),
        "expected_by": str(row["expected_by"]),
        "status": str(row.get("status") or "pending"),
        "suggested_action": str(row.get("suggested_action") or ""),
        "draft_reply": str(row.get("draft_reply") or ""),
        "created_at": str(row.get("created_at") or ""),
    }
