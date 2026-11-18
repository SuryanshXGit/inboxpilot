"""Comprehensive unit and integration test suite for InboxPilot 2.0 API routes."""

from __future__ import annotations

import os
import uuid
from typing import Any
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///test_suite.db")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-thirty-two-bytes-long")

from app.core.security import create_access_token
from app.db import client as db_client
from app.main import app
from app.services import auth_service, email_service, task_service

# Run test suite directly against resilient local engine for sub-second execution
db_client._pg_available = False


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    test_user_id = str(uuid.uuid4())
    # Create user in database
    token, user = auth_service.register_user(
        f"test-{test_user_id[:8]}@example.com",
        "SecurePassword123!",
        "Test Engineer",
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Authentication & User Profile Tests
# ---------------------------------------------------------------------------


def test_auth_register_and_login_flow(client: TestClient) -> None:
    email = f"user-{uuid.uuid4().hex[:8]}@testdomain.com"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Alex"},
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == email.lower()

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Wrong password
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401


def test_auth_duplicate_email_rejected(client: TestClient) -> None:
    email = f"dup-{uuid.uuid4().hex[:8]}@testdomain.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    res2 = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    assert res2.status_code == 409


def test_profile_and_preferences(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Get profile
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert "email" in me.json()

    # Update profile & preferences
    up = client.put(
        "/api/v1/auth/profile",
        headers=auth_headers,
        json={"display_name": "Updated Name", "preferences": {"theme": "midnight", "ai_tone": "concise"}},
    )
    assert up.status_code == 200
    assert up.json()["display_name"] == "Updated Name"
    assert up.json()["preferences"]["theme"] == "midnight"


def test_change_password_and_account_lifecycle(client: TestClient) -> None:
    email = f"lifecycle-{uuid.uuid4().hex[:8]}@testdomain.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "InitialPass123!"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Change password
    ch = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "InitialPass123!", "new_password": "NewSecretPass123!"},
    )
    assert ch.status_code == 200

    # Login with new password
    login_new = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "NewSecretPass123!"},
    )
    assert login_new.status_code == 200

    # Data export
    exp = client.get("/api/v1/auth/export", headers=headers)
    assert exp.status_code == 200
    assert "user" in exp.json()

    # Delete account
    del_res = client.delete("/api/v1/auth/me", headers=headers)
    assert del_res.status_code == 200


# ---------------------------------------------------------------------------
# 2. Smart Inbox & Email Management Tests
# ---------------------------------------------------------------------------


def test_email_accounts_and_sync(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Connect account
    conn = client.post(
        "/api/v1/emails/accounts",
        headers=auth_headers,
        json={"provider": "demo", "email_address": "alex@venturex.io"},
    )
    assert conn.status_code == 201
    account_id = conn.json()["id"]

    # List accounts
    accs = client.get("/api/v1/emails/accounts", headers=auth_headers)
    assert accs.status_code == 200
    assert len(accs.json()) >= 1

    # List threads (seeded during sync)
    threads_res = client.get("/api/v1/emails/threads", headers=auth_headers)
    assert threads_res.status_code == 200
    data = threads_res.json()
    assert data["total_count"] >= 1
    assert len(data["threads"]) >= 1

    thread = data["threads"][0]
    thread_id = thread["id"]

    # Get thread detail
    detail = client.get(f"/api/v1/emails/threads/{thread_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert "messages" in detail.json()
    assert len(detail.json()["messages"]) >= 1

    # Update category
    cat_res = client.patch(
        f"/api/v1/emails/threads/{thread_id}/category",
        headers=auth_headers,
        json={"category": "Finance"},
    )
    assert cat_res.status_code == 200
    assert cat_res.json()["thread"]["category"] == "Finance"

    # Toggle star
    star_res = client.post(f"/api/v1/emails/threads/{thread_id}/star", headers=auth_headers)
    assert star_res.status_code == 200


def test_email_filtering_and_search(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Ensure account and initial threads exist
    client.post(
        "/api/v1/emails/accounts",
        headers=auth_headers,
        json={"provider": "demo", "email_address": "test@filter.com"},
    )

    # Filter priority HIGH
    high = client.get("/api/v1/emails/threads?priority=high", headers=auth_headers)
    assert high.status_code == 200
    for t in high.json()["threads"]:
        assert t["priority"] == "HIGH"

    # Search
    search = client.get("/api/v1/emails/threads?search=audit", headers=auth_headers)
    assert search.status_code == 200


# ---------------------------------------------------------------------------
# 3. Tasks & Projects Tests
# ---------------------------------------------------------------------------


def test_tasks_crud_and_kanban(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Create task
    t_res = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Review investment prospectus",
            "description": "Examine equity dilution and liquidation preferences",
            "due_at": "Tomorrow",
            "priority": "high",
            "status": "todo",
        },
    )
    assert t_res.status_code == 201
    task = t_res.json()
    task_id = task["id"]
    assert task["title"] == "Review investment prospectus"

    # Kanban board
    kb = client.get("/api/v1/tasks/kanban", headers=auth_headers)
    assert kb.status_code == 200
    assert "todo" in kb.json()
    assert "in_progress" in kb.json()
    assert kb.json()["total_tasks"] >= 1

    # Update task status
    up = client.put(
        f"/api/v1/tasks/{task_id}",
        headers=auth_headers,
        json={"status": "completed"},
    )
    assert up.status_code == 200
    assert up.json()["status"] == "completed"

    # Delete task
    del_res = client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert del_res.status_code == 200


def test_email_to_task_approval(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Approve extracted task
    res = client.post(
        "/api/v1/tasks/approve-extracted",
        headers=auth_headers,
        json={
            "title": "Confirm Venue Audio Equipment with Dean",
            "description": "Extracted from Seminar Hall email.",
            "due_at": "Today at 4 PM",
            "priority": "urgent",
            "confidence": 0.94,
        },
    )
    assert res.status_code == 200
    task = res.json()
    assert task["title"] == "Confirm Venue Audio Equipment with Dean"
    assert task["confidence"] == 0.94


# ---------------------------------------------------------------------------
# 4. Calendar & Meeting Intelligence Tests
# ---------------------------------------------------------------------------


def test_calendar_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    ev_res = client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={
            "title": "Board of Directors Q4 Strategy",
            "description": "Financial forecast and product velocity",
            "location": "Boardroom 1",
            "starts_at": "2026-11-20 14:00",
            "ends_at": "2026-11-20 15:30",
            "priority": "high",
        },
    )
    assert ev_res.status_code == 201
    ev_id = ev_res.json()["id"]

    events = client.get("/api/v1/calendar/events", headers=auth_headers)
    assert events.status_code == 200
    assert len(events.json()) >= 1

    # Delete event
    client.delete(f"/api/v1/calendar/events/{ev_id}", headers=auth_headers)


# ---------------------------------------------------------------------------
# 5. Productivity Intelligence Tests
# ---------------------------------------------------------------------------


def test_productivity_endpoints(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Daily briefing
    briefing = client.get("/api/v1/productivity/briefing", headers=auth_headers)
    assert briefing.status_code == 200
    b_data = briefing.json()
    assert "summary_greeting" in b_data
    assert "todays_tasks" in b_data

    # Deadline radar
    radar = client.get("/api/v1/productivity/deadline-radar", headers=auth_headers)
    assert radar.status_code == 200
    assert isinstance(radar.json(), list)

    # Waiting for
    waiting = client.get("/api/v1/productivity/waiting-for", headers=auth_headers)
    assert waiting.status_code == 200
    assert len(waiting.json()) >= 1

    # Focus mode
    focus = client.get("/api/v1/productivity/focus", headers=auth_headers)
    assert focus.status_code == 200
    assert "focus_items" in focus.json()


# ---------------------------------------------------------------------------
# 6. Knowledge Hub & Follow-ups Tests
# ---------------------------------------------------------------------------


def test_knowledge_hub(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Create knowledge item
    k_res = client.post(
        "/api/v1/knowledge",
        headers=auth_headers,
        json={
            "title": "AWS S3 CORS Configuration Guide",
            "content": "Allow PutObject and GetObject with Authorization headers.",
            "category": "Infrastructure",
            "tags": ["aws", "s3", "cloud"],
        },
    )
    assert k_res.status_code == 201
    k_id = k_res.json()["id"]

    # List knowledge items
    items = client.get("/api/v1/knowledge", headers=auth_headers)
    assert items.status_code == 200
    assert len(items.json()) >= 1

    # Search
    search = client.get("/api/v1/knowledge?search=CORS", headers=auth_headers)
    assert search.status_code == 200
    assert len(search.json()) >= 1

    client.delete(f"/api/v1/knowledge/{k_id}", headers=auth_headers)


def test_follow_ups_management(client: TestClient, auth_headers: dict[str, str]) -> None:
    fu_res = client.post(
        "/api/v1/follow-ups",
        headers=auth_headers,
        json={
            "recipient": "Sarah Lin",
            "subject": "Design token export for mobile",
            "expected_by": "Friday 12 PM",
            "suggested_action": "Check if Figma variables have been published",
        },
    )
    assert fu_res.status_code == 201
    fu_id = fu_res.json()["id"]

    # Patch status
    up = client.patch(
        f"/api/v1/follow-ups/{fu_id}",
        headers=auth_headers,
        json={"status": "replied"},
    )
    assert up.status_code == 200
    assert up.json()["status"] == "replied"


# ---------------------------------------------------------------------------
# 7. Automation Studio Tests
# ---------------------------------------------------------------------------


def test_automation_studio(client: TestClient, auth_headers: dict[str, str]) -> None:
    # List initial seeded workflows
    wfs = client.get("/api/v1/automations/workflows", headers=auth_headers)
    assert wfs.status_code == 200
    assert len(wfs.json()) >= 1
    wf = wfs.json()[0]
    wf_id = wf["id"]

    # Toggle workflow
    toggled = client.post(f"/api/v1/automations/workflows/{wf_id}/toggle", headers=auth_headers)
    assert toggled.status_code == 200

    # Test workflow run
    test_run = client.post(f"/api/v1/automations/workflows/{wf_id}/test", headers=auth_headers)
    assert test_run.status_code == 200
    assert test_run.json()["status"] == "success"

    # List runs
    runs = client.get("/api/v1/automations/runs", headers=auth_headers)
    assert runs.status_code == 200
    assert len(runs.json()) >= 1


# ---------------------------------------------------------------------------
# 8. Analytics Overview Tests
# ---------------------------------------------------------------------------


def test_analytics_overview(client: TestClient, auth_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/analytics/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "emails_processed" in data
    assert "tasks_total" in data
    assert "categories_breakdown" in data
    assert "weekly_trend" in data
