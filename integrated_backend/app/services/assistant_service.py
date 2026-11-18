"""Context-aware AI Personal Assistant service."""

from __future__ import annotations

from typing import Any

from app.ai_engine import graph
from app.ai_engine.models import AssistantChatResult
from app.db.client import get_db
from app.services import calendar_service, email_service, task_service


async def answer_assistant_query(
    user_id: str,
    query: str,
    include_emails: bool = True,
    include_tasks: bool = True,
    include_calendar: bool = True,
) -> dict[str, Any]:
    """Retrieve authorized user data context and run structured AI assistant workflow."""
    context_sections: list[str] = []

    if include_emails:
        threads_data = email_service.get_threads(user_id, page_size=10)
        email_lines = [
            f"- [Email ID: {t['id']}] From: {t['snippet'][:80]} | Subject: {t['subject']} | Priority: {t['priority']} ({t['priority_reason']}) | Category: {t['category']}"
            for t in threads_data["threads"]
        ]
        context_sections.append("### RECENT EMAILS IN USER'S INBOX:\n" + "\n".join(email_lines))

    if include_tasks:
        tasks = task_service.list_tasks(user_id)
        task_lines = [
            f"- [Task ID: {t['id']}] Title: {t['title']} | Due: {t['due_at']} | Priority: {t['priority']} | Status: {t['status']}"
            for t in tasks
        ]
        context_sections.append("### USER'S TASKS & TO-DOS:\n" + "\n".join(task_lines))

    if include_calendar:
        events = calendar_service.list_events(user_id)
        event_lines = [
            f"- [Event ID: {e['id']}] Title: {e['title']} | When: {e['starts_at']} to {e['ends_at']} | Location: {e['location']} | Priority: {e['priority']}"
            for e in events
        ]
        context_sections.append("### UPCOMING CALENDAR EVENTS:\n" + "\n".join(event_lines))

    full_context = "\n\n".join(context_sections)

    result: AssistantChatResult = await graph.run_assistant_chat(
        query=query,
        context_text=full_context,
    )

    return {
        "answer": result.answer,
        "sources": result.sources,
        "suggested_actions": result.suggested_actions,
        "query": query,
    }
