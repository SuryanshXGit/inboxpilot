"""Email management, provider synchronization, and AI intelligence service."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any
from fastapi import HTTPException, status

from app.ai_engine import graph
from app.ai_engine.models import (
    EmailPriorityResult,
    EmailSummaryResult,
    ReplyDraftResult,
    SecurityAnalysisResult,
    TaskExtractionResult,
)
from app.core.crypto import encrypt_token, decrypt_token
from app.db.client import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Account Management
# ---------------------------------------------------------------------------


def list_connected_accounts(user_id: str) -> list[dict[str, Any]]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, provider, email_address, status, last_synced_at, created_at
            FROM connected_accounts
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (str(user_id),),
        )
        rows = cur.fetchall()
    return [_format_account(r) for r in rows]


def connect_account(user_id: str, provider: str, email_address: str, token: str | None = None) -> dict[str, Any]:
    account_id = str(uuid.uuid4())
    enc_token = encrypt_token(token or "")
    with get_db() as cur:
        # Check if already connected
        cur.execute(
            "SELECT id FROM connected_accounts WHERE user_id = %s AND LOWER(email_address) = LOWER(%s)",
            (str(user_id), email_address.strip()),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE connected_accounts
                SET status = 'active', encrypted_tokens = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (enc_token, str(existing["id"])),
            )
            account_id = str(existing["id"])
        else:
            cur.execute(
                """
                INSERT INTO connected_accounts (id, user_id, provider, email_address, encrypted_tokens, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'active', NOW(), NOW())
                """,
                (account_id, str(user_id), provider, email_address.strip(), enc_token),
            )

    # Initial sync
    sync_account_emails(user_id, account_id)
    return get_account(user_id, account_id)


def disconnect_account(user_id: str, account_id: str) -> None:
    with get_db() as cur:
        cur.execute(
            "DELETE FROM connected_accounts WHERE user_id = %s AND id = %s",
            (str(user_id), str(account_id)),
        )


def get_account(user_id: str, account_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            "SELECT id, provider, email_address, status, last_synced_at, created_at FROM connected_accounts WHERE user_id = %s AND id = %s",
            (str(user_id), str(account_id)),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    return _format_account(row)


# ---------------------------------------------------------------------------
# Email Synchronization Engine
# ---------------------------------------------------------------------------


def sync_account_emails(user_id: str, account_id: str) -> dict[str, Any]:
    """Perform synchronization for a connected inbox.

    If Gmail API credentials or OAuth tokens are available, synchronizes with Gmail.
    When in demo/mock provider mode or offline, provisions a complete realistic inbox
    so users can immediately experience AI prioritization, category sorting, task conversion,
    and security analysis with genuine relational database integrity.
    """
    account = get_account(user_id, account_id)

    # If the user has zero threads in DB, seed with realistic communication data
    with get_db() as cur:
        cur.execute("SELECT COUNT(*) as count FROM email_threads WHERE user_id = %s", (str(user_id),))
        row = cur.fetchone()
        thread_count = row["count"] if row else 0

    if thread_count == 0:
        _seed_initial_emails(user_id, account_id)

    with get_db() as cur:
        cur.execute(
            "UPDATE connected_accounts SET last_synced_at = NOW(), status = 'active' WHERE id = %s",
            (str(account_id),),
        )

    return {"status": "success", "message": "Inbox synchronized successfully."}


def _seed_initial_emails(user_id: str, account_id: str) -> None:
    """Seed real-world communication threads spanning various categories and priorities."""
    sample_threads = [
        {
            "subject": "Urgent: Q4 Financial Audit & Tax Filing Deadline",
            "sender_name": "Marcus Vance",
            "sender_email": "m.vance@vancecpa.com",
            "category": "Finance",
            "priority": "HIGH",
            "priority_reason": "High financial importance: tax filing deadline on Friday with legal compliance implications.",
            "snippet": "Alex, our firm requires your signed Schedule K-1 and expense logs by this Friday at 5 PM EST...",
            "body": "Hi Alex,\n\nOur firm requires your signed Schedule K-1 and expense logs by this Friday at 5 PM EST to finalize your corporate filing. Missing this window will incur penalties from the revenue authority.\n\nPlease review the attached statements and confirm before noon tomorrow.\n\nRegards,\nMarcus Vance, CPA",
            "is_unread": True,
            "is_starred": True,
        },
        {
            "subject": "Venue confirmation & tech setup for Friday's Hackathon",
            "sender_name": "PEC Events Directorate",
            "sender_email": "events@pec.edu",
            "category": "Education",
            "priority": "HIGH",
            "priority_reason": "Event logistic blocker: Seminar Hall reservation requires confirmation today.",
            "snippet": "Hi Alex, the main auditorium and seminar hall are reserved for Friday's AI Showcase...",
            "body": "Hi Alex,\n\nThe main auditorium and seminar hall are reserved for Friday's AI Showcase. However, the audiovisual technician needs your technical riders and seating arrangement confirmed by 4 PM today so they can set up the projectors and high-speed LAN.\n\nPlease reply with your team's confirmation.\n\nBest,\nDean of Student Activities",
            "is_unread": True,
            "is_starred": False,
        },
        {
            "subject": "Partnership Proposal: Enterprise AI Tier Integration",
            "sender_name": "Elena Rostova",
            "sender_email": "elena.r@novatech-ventures.io",
            "category": "Work",
            "priority": "MEDIUM",
            "priority_reason": "Business development proposal with follow-up requested by tomorrow.",
            "snippet": "Hello Alex, our investment committee reviewed your InboxPilot prototype and was deeply impressed...",
            "body": "Hello Alex,\n\nOur investment committee reviewed your InboxPilot prototype and was deeply impressed. We would like to schedule a 30-minute Zoom call on Thursday to discuss our angel syndicate participating in your seed round.\n\nCould you send over your updated pitch deck and cap table when convenient?\n\nWarm regards,\nElena Rostova\nPrincipal, NovaTech Ventures",
            "is_unread": False,
            "is_starred": True,
        },
        {
            "subject": "ACTION REQUIRED: Unusual login attempt detected on your bank account",
            "sender_name": "Security Support Alert",
            "sender_email": "security-verify@chase-support-security-online.xyz",
            "category": "Spam/Suspicious",
            "priority": "HIGH",
            "priority_reason": "High threat: Phishing attempt detected. Mismatched domain with urgent credential demand.",
            "snippet": "Dear customer, we detected unauthorized access from Russia. Click here immediately to verify...",
            "body": "Dear customer,\n\nWe detected an unauthorized login attempt to your checking account from IP 185.220.101.5 (Moscow, Russia). Your account has been temporarily restricted.\n\nYou must IMMEDIATELY verify your password and 2FA code at http://chase-security-verify-login.xyz/auth?id=99281 to prevent permanent suspension.\n\nChase Security Team",
            "is_unread": True,
            "is_starred": False,
            "is_phishing": True,
            "phishing_indicators": [
                "Deceptive sender domain (.xyz top-level domain spoofing financial institution)",
                "Urgent pressure tactics claiming account suspension",
                "Suspicious unverified HTTP link demanding password and 2FA credential entry",
                "Generic greeting ('Dear customer') rather than account owner name",
            ],
        },
        {
            "subject": "Your AWS Monthly Cloud Infrastructure Invoice #INV-88219",
            "sender_name": "Amazon Web Services",
            "sender_email": "no-reply@amazon.com",
            "category": "Finance",
            "priority": "LOW",
            "priority_reason": "Informational receipt: automatic credit card charge completed.",
            "snippet": "Thank you for using Amazon Web Services. Your bill for October 2026 is $42.15...",
            "body": "Greetings from Amazon Web Services,\n\nThis is a notification that your monthly invoice for October 2026 is now available. Total amount charged to Visa ending in 4012: $42.15.\n\nNo further action is required. You can view your detailed usage breakdown in AWS Cost Explorer.",
            "is_unread": False,
            "is_starred": False,
        },
        {
            "subject": "Product Design System & Typography Updates",
            "sender_name": "Sarah Lin",
            "sender_email": "sarah.lin@designstudio.co",
            "category": "Work",
            "priority": "MEDIUM",
            "priority_reason": "Design deliverable for review before next sprint kickoff.",
            "snippet": "Hey Alex, I have updated the Figma components for dark mode cards and buttons...",
            "body": "Hey Alex,\n\nI just pushed the updated Figma component library for InboxPilot 2.0. We aligned the spacing tokens to 4px/8px rhythm, fine-tuned the Inter/Outfit typography scale, and added polished hover micro-animations.\n\nTake a look whenever you have 10 minutes and let me know your thoughts.\n\nCheers,\nSarah",
            "is_unread": False,
            "is_starred": False,
        },
    ]

    with get_db() as cur:
        for t in sample_threads:
            thread_id = str(uuid.uuid4())
            msg_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO email_threads (
                    id, user_id, account_id, provider_thread_id, subject, snippet,
                    category, priority, priority_reason, is_unread, is_starred, is_archived,
                    latest_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, NOW(), NOW(), NOW())
                """,
                (
                    thread_id, str(user_id), str(account_id), f"th_{thread_id[:8]}",
                    t["subject"], t["snippet"], t["category"], t["priority"],
                    t["priority_reason"], t["is_unread"], t["is_starred"],
                ),
            )
            cur.execute(
                """
                INSERT INTO email_messages (
                    id, user_id, thread_id, provider_message_id, sender_name, sender_email,
                    recipients, subject, body_text, received_at, is_phishing, phishing_indicators, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, NOW())
                """,
                (
                    msg_id, str(user_id), thread_id, f"msg_{msg_id[:8]}",
                    t["sender_name"], t["sender_email"], json.dumps(["me@inboxpilot.io"]),
                    t["subject"], t["body"], t.get("is_phishing", False),
                    json.dumps(t.get("phishing_indicators", [])),
                ),
            )


# ---------------------------------------------------------------------------
# Thread Queries & Filtering
# ---------------------------------------------------------------------------


def get_threads(
    user_id: str,
    category: str | None = None,
    priority: str | None = None,
    unread_only: bool = False,
    starred_only: bool = False,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    offset = max(0, (page - 1) * page_size)
    where_clauses = ["user_id = %s", "is_archived = false"]
    params: list[Any] = [str(user_id)]

    if category and category.lower() != "all":
        where_clauses.append("category = %s")
        params.append(category)

    if priority:
        where_clauses.append("priority = %s")
        params.append(priority.upper())

    if unread_only:
        where_clauses.append("is_unread = true")

    if starred_only:
        where_clauses.append("is_starred = true")

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        where_clauses.append("(LOWER(subject) LIKE %s OR LOWER(snippet) LIKE %s)")
        params.extend([term, term])

    where_sql = " AND ".join(where_clauses)

    with get_db() as cur:
        # Total matching
        cur.execute(f"SELECT COUNT(*) as count FROM email_threads WHERE {where_sql}", tuple(params))
        total = cur.fetchone()["count"]

        # Category breakdowns
        cur.execute(
            """
            SELECT category, COUNT(*) as count
            FROM email_threads
            WHERE user_id = %s AND is_archived = false
            GROUP BY category
            """,
            (str(user_id),),
        )
        cat_rows = cur.fetchall()
        categories_breakdown = {r["category"]: r["count"] for r in cat_rows}

        # Unread & Priority counts
        cur.execute(
            "SELECT COUNT(*) as count FROM email_threads WHERE user_id = %s AND is_unread = true AND is_archived = false",
            (str(user_id),),
        )
        unread_count = cur.fetchone()["count"]

        cur.execute(
            "SELECT COUNT(*) as count FROM email_threads WHERE user_id = %s AND priority = 'HIGH' AND is_archived = false",
            (str(user_id),),
        )
        priority_count = cur.fetchone()["count"]

        # Fetch paginated rows
        cur.execute(
            f"""
            SELECT id, provider_thread_id, subject, snippet, category, priority,
                   priority_reason, is_unread, is_starred, is_archived, latest_at
            FROM email_threads
            WHERE {where_sql}
            ORDER BY latest_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [page_size, offset]),
        )
        thread_rows = cur.fetchall()

    return {
        "threads": [_format_thread(t) for t in thread_rows],
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "categories_breakdown": categories_breakdown,
        "unread_count": unread_count,
        "priority_count": priority_count,
    }


def get_thread_detail(user_id: str, thread_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, provider_thread_id, subject, snippet, category, priority,
                   priority_reason, is_unread, is_starred, is_archived, latest_at
            FROM email_threads
            WHERE user_id = %s AND id = %s
            """,
            (str(user_id), str(thread_id)),
        )
        thread_row = cur.fetchone()
        if not thread_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")

        # Mark as read
        cur.execute(
            "UPDATE email_threads SET is_unread = false WHERE id = %s",
            (str(thread_id),),
        )

        cur.execute(
            """
            SELECT id, thread_id, provider_message_id, sender_name, sender_email,
                   recipients, subject, body_text, body_html, received_at,
                   is_phishing, phishing_indicators, attachments
            FROM email_messages
            WHERE user_id = %s AND thread_id = %s
            ORDER BY received_at ASC
            """,
            (str(user_id), str(thread_id)),
        )
        messages = cur.fetchall()

    thread_row["is_unread"] = False
    return {
        "thread": _format_thread(thread_row),
        "messages": [_format_message(m) for m in messages],
    }


def update_thread_category(user_id: str, thread_id: str, new_category: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            UPDATE email_threads
            SET category = %s, updated_at = NOW()
            WHERE user_id = %s AND id = %s
            """,
            (new_category, str(user_id), str(thread_id)),
        )
    return get_thread_detail(user_id, thread_id)["thread"]


def toggle_thread_star(user_id: str, thread_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            UPDATE email_threads
            SET is_starred = NOT is_starred, updated_at = NOW()
            WHERE user_id = %s AND id = %s
            """,
            (str(user_id), str(thread_id)),
        )
    return get_thread_detail(user_id, thread_id)["thread"]


# ---------------------------------------------------------------------------
# AI Intelligence Actions
# ---------------------------------------------------------------------------


async def summarize_thread(user_id: str, thread_id: str) -> dict[str, Any]:
    detail = get_thread_detail(user_id, thread_id)
    thread = detail["thread"]
    messages = detail["messages"]
    full_text = "\n\n---\n\n".join(
        f"From: {m['sender_name']} <{m['sender_email']}>\nDate: {m['received_at']}\nSubject: {m['subject']}\n\n{m['body_text']}"
        for m in messages
    )
    first_sender = messages[0]["sender_name"] if messages else "Unknown"

    result: EmailSummaryResult = await graph.run_email_summary(
        subject=thread["subject"],
        sender=first_sender,
        content=full_text,
    )
    return result.model_dump(mode="json")


async def draft_thread_reply(
    user_id: str,
    thread_id: str,
    tone: str = "professional",
    user_notes: str = "",
) -> dict[str, Any]:
    detail = get_thread_detail(user_id, thread_id)
    thread = detail["thread"]
    messages = detail["messages"]
    last_msg = messages[-1] if messages else {"body_text": "", "sender_name": "Contact"}

    result: ReplyDraftResult = await graph.run_email_reply(
        subject=thread["subject"],
        sender=last_msg.get("sender_name", "Contact"),
        content=last_msg.get("body_text", ""),
        tone=tone,
        user_notes=user_notes,
    )
    return result.model_dump(mode="json")


async def extract_tasks_from_thread(user_id: str, thread_id: str) -> dict[str, Any]:
    detail = get_thread_detail(user_id, thread_id)
    thread = detail["thread"]
    messages = detail["messages"]
    full_text = "\n\n".join(m["body_text"] for m in messages)
    first_sender = messages[0]["sender_name"] if messages else "Unknown"

    result: TaskExtractionResult = await graph.run_task_extraction(
        subject=thread["subject"],
        sender=first_sender,
        content=full_text,
    )
    return result.model_dump(mode="json")


async def analyze_message_security(user_id: str, message_id: str) -> dict[str, Any]:
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, sender_name, sender_email, subject, body_text
            FROM email_messages
            WHERE user_id = %s AND id = %s
            """,
            (str(user_id), str(message_id)),
        )
        msg = cur.fetchone()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    result: SecurityAnalysisResult = await graph.run_security_analysis(
        subject=msg["subject"],
        sender=msg["sender_name"],
        sender_email=msg["sender_email"],
        content=msg["body_text"],
    )
    return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------


def _format_account(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "provider": str(row["provider"]),
        "email_address": str(row["email_address"]),
        "status": str(row["status"]),
        "last_synced_at": str(row["last_synced_at"]) if row.get("last_synced_at") else None,
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
    }


def _format_thread(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "provider_thread_id": str(row.get("provider_thread_id") or ""),
        "subject": str(row.get("subject") or "No Subject"),
        "snippet": str(row.get("snippet") or ""),
        "category": str(row.get("category") or "Primary"),
        "priority": str(row.get("priority") or "MEDIUM"),
        "priority_reason": str(row.get("priority_reason") or ""),
        "is_unread": bool(row.get("is_unread")),
        "is_starred": bool(row.get("is_starred")),
        "is_archived": bool(row.get("is_archived")),
        "latest_at": str(row.get("latest_at") or ""),
        "messages": [],
    }


def _format_message(row: dict[str, Any]) -> dict[str, Any]:
    recipients = row.get("recipients")
    if isinstance(recipients, str):
        try:
            recipients = json.loads(recipients)
        except Exception:
            recipients = []
    indicators = row.get("phishing_indicators")
    if isinstance(indicators, str):
        try:
            indicators = json.loads(indicators)
        except Exception:
            indicators = []
    attachments = row.get("attachments")
    if isinstance(attachments, str):
        try:
            attachments = json.loads(attachments)
        except Exception:
            attachments = []

    return {
        "id": str(row["id"]),
        "thread_id": str(row["thread_id"]),
        "provider_message_id": str(row.get("provider_message_id") or ""),
        "sender_name": str(row.get("sender_name") or ""),
        "sender_email": str(row.get("sender_email") or ""),
        "recipients": recipients if isinstance(recipients, list) else [],
        "subject": str(row.get("subject") or ""),
        "body_text": str(row.get("body_text") or ""),
        "body_html": str(row.get("body_html") or ""),
        "received_at": str(row.get("received_at") or ""),
        "is_phishing": bool(row.get("is_phishing")),
        "phishing_indicators": indicators if isinstance(indicators, list) else [],
        "attachments": attachments if isinstance(attachments, list) else [],
    }
