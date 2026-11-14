"""Tests for the InboxPilot workspace endpoints.

The fake cursor implements only the two SQL statements used by
``workspace_service``; authentication is exercised with a signed token so the
test stays focused on the new routes.
"""

from __future__ import annotations

import itertools
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")

from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.services import workspace_service  # noqa: E402

USER_ID = str(uuid.UUID(int=101))
OTHER_USER_ID = str(uuid.UUID(int=202))


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeWorkspaceDatabase:
    def __init__(self) -> None:
        self.workspaces: dict[str, dict[str, Any]] = {}
        self._ids = itertools.count(1)

    def execute(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        query = " ".join(sql.split()).lower()
        params = tuple(params or ())

        if query.startswith("select state, updated_at from inboxpilot_workspaces"):
            row = self.workspaces.get(str(params[0]))
            return [dict(row)] if row else []

        if query.startswith("insert into inboxpilot_workspaces"):
            user_id, state = params
            state = getattr(state, "obj", state)
            row = {
                "state": state,
                "updated_at": _now(),
            }
            self.workspaces[str(user_id)] = row
            return [dict(row)]

        raise AssertionError(f"Unhandled SQL in test fake: {query}")


class FakeCursor:
    def __init__(self, database: FakeWorkspaceDatabase) -> None:
        self.database = database
        self._rows: list[dict[str, Any]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._rows = self.database.execute(sql, params or ())

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None


@pytest.fixture(autouse=True)
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeWorkspaceDatabase:
    database = FakeWorkspaceDatabase()

    @contextmanager
    def fake_get_db():
        yield FakeCursor(database)

    monkeypatch.setattr(workspace_service, "get_db", fake_get_db)
    return database


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _headers(user_id: str = USER_ID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _sample_state() -> dict[str, Any]:
    return {
        "tasks": [
            {"text": "Confirm event venue booking", "due": "Today", "done": False}
        ],
        "events": [
            {
                "date": "2026-11-15",
                "name": "Sponsor call",
                "time": "13:00",
                "place": "Online",
                "priority": "high",
            }
        ],
        "messages": [
            {
                "name": "PEC Events Team",
                "initial": "PE",
                "subject": "Venue availability",
                "preview": "The seminar hall is available.",
                "priority": "HIGH",
                "body": "Please confirm the booking.",
                "when": "9:42 AM",
            }
        ],
        "notes": [
            {"title": "Sponsor summary", "details": "Email", "body": "Deck due tomorrow."}
        ],
        "approval_state": "pending",
    }


def test_workspace_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/workspace").status_code == 401
    assert client.put("/api/v1/workspace", json=_sample_state()).status_code == 401


def test_empty_workspace_has_no_updated_at(client: TestClient) -> None:
    response = client.get("/api/v1/workspace", headers=_headers())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tasks"] == []
    assert body["events"] == []
    assert body["messages"] == []
    assert body["notes"] == []
    assert body["approval_state"] == "pending"
    assert body["updated_at"] is None


def test_workspace_round_trip(client: TestClient) -> None:
    payload = _sample_state()

    saved = client.put("/api/v1/workspace", json=payload, headers=_headers())
    assert saved.status_code == 200, saved.text
    assert saved.json()["tasks"] == payload["tasks"]
    assert saved.json()["updated_at"] is not None

    loaded = client.get("/api/v1/workspace", headers=_headers())
    assert loaded.status_code == 200, loaded.text
    for key, value in payload.items():
        assert loaded.json()[key] == value


def test_workspace_is_scoped_per_user(client: TestClient) -> None:
    client.put("/api/v1/workspace", json=_sample_state(), headers=_headers())

    other = client.get("/api/v1/workspace", headers=_headers(OTHER_USER_ID))
    assert other.status_code == 200
    assert other.json()["tasks"] == []
    assert other.json()["updated_at"] is None


def test_workspace_rejects_invalid_payload(client: TestClient) -> None:
    bad_event = _sample_state()
    bad_event["events"][0]["date"] = "15-11-2026"
    assert (
        client.put("/api/v1/workspace", json=bad_event, headers=_headers()).status_code
        == 422
    )

    impossible_date = _sample_state()
    impossible_date["events"][0]["date"] = "2026-02-30"
    assert (
        client.put(
            "/api/v1/workspace", json=impossible_date, headers=_headers()
        ).status_code
        == 422
    )

    bad_approval = _sample_state()
    bad_approval["approval_state"] = "maybe"
    assert (
        client.put("/api/v1/workspace", json=bad_approval, headers=_headers()).status_code
        == 422
    )

    unknown_key = _sample_state()
    unknown_key["extra"] = True
    assert (
        client.put("/api/v1/workspace", json=unknown_key, headers=_headers()).status_code
        == 422
    )


def test_workspace_rejects_blank_required_text(client: TestClient) -> None:
    blank_task = _sample_state()
    blank_task["tasks"][0]["text"] = "   "
    assert (
        client.put("/api/v1/workspace", json=blank_task, headers=_headers()).status_code
        == 422
    )

    blank_event = _sample_state()
    blank_event["events"][0]["name"] = "  "
    assert (
        client.put("/api/v1/workspace", json=blank_event, headers=_headers()).status_code
        == 422
    )

    blank_message = _sample_state()
    blank_message["messages"][0]["name"] = "\t"
    assert (
        client.put("/api/v1/workspace", json=blank_message, headers=_headers()).status_code
        == 422
    )

    blank_note = _sample_state()
    blank_note["notes"][0]["title"] = "\n"
    assert (
        client.put("/api/v1/workspace", json=blank_note, headers=_headers()).status_code
        == 422
    )


def test_workspace_trims_required_text(client: TestClient) -> None:
    payload = _sample_state()
    payload["tasks"][0]["text"] = "  Confirm venue  "
    payload["events"][0]["name"] = "  Sponsor call  "
    payload["messages"][0]["name"] = "  PEC Events Team  "
    payload["notes"][0]["title"] = "  Sponsor summary  "

    saved = client.put("/api/v1/workspace", json=payload, headers=_headers())
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["tasks"][0]["text"] == "Confirm venue"
    assert body["events"][0]["name"] == "Sponsor call"
    assert body["messages"][0]["name"] == "PEC Events Team"
    assert body["notes"][0]["title"] == "Sponsor summary"


def test_workspace_accepts_ui_due_length(client: TestClient) -> None:
    payload = _sample_state()
    payload["tasks"][0]["due"] = "x" * 220

    saved = client.put("/api/v1/workspace", json=payload, headers=_headers())
    assert saved.status_code == 200, saved.text
    assert saved.json()["tasks"][0]["due"] == "x" * 220


def test_workspace_responses_are_not_cached(client: TestClient) -> None:
    loaded = client.get("/api/v1/workspace", headers=_headers())
    assert loaded.headers["cache-control"] == "no-store"

    saved = client.put("/api/v1/workspace", json=_sample_state(), headers=_headers())
    assert saved.headers["cache-control"] == "no-store"
