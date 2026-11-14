"""Integration tests across the API, service layer and typed AI engine.

Provider calls and database access are faked. These tests prove that the AI
engine's Pydantic results are persisted and returned correctly by Person 1's
existing endpoints.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.ai_engine import providers
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.services import learning_service
from tests.test_api import FakeCursor, FakeDatabase

LESSON_PAYLOAD = {
    "title": "Adding numbers",
    "explanation": "Two plus two equals four.",
    "key_points": ["Numbers can be added", "The result is called a sum"],
    "examples": ["2 + 2 = 4"],
    "check_for_understanding": "What is 3 + 1?",
    "suggested_next_topic": "Subtraction",
}

QUIZ_PAYLOAD = {
    "topic": "arithmetic",
    "questions": [
        {
            "question": "What is 2 + 2?",
            "options": ["3", "4", "5", "6"],
            "correct_option_index": 1,
            "explanation": "2 + 2 = 4.",
            "difficulty": "easy",
        },
        {
            "question": "What is 3 + 1?",
            "options": ["2", "3", "4", "5"],
            "correct_option_index": 2,
            "explanation": "3 + 1 = 4.",
            "difficulty": "easy",
        },
    ],
}

EVALUATION_PAYLOAD = {
    "is_correct": True,
    "score": 0.9,
    "feedback": "Correct, with clear reasoning.",
    "misconception": None,
    "next_step": "Try a two-digit addition problem.",
}


class FakeProvider:
    name = "fake"

    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.outputs) - 1)
        output = self.outputs[index]
        if isinstance(output, Exception):
            raise output
        return output


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeDatabase:
    database = FakeDatabase()

    @contextmanager
    def fake_get_db():
        yield FakeCursor(database)

    monkeypatch.setattr(learning_service, "get_db", fake_get_db)
    return database


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_PRIMARY_PROVIDER", "openai")
    monkeypatch.setattr(settings, "AI_FALLBACK_PROVIDER", "none")
    monkeypatch.setattr(settings, "AI_MAX_RETRIES", 0)
    monkeypatch.setattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.0)


def _install_provider(monkeypatch: pytest.MonkeyPatch, provider: FakeProvider) -> None:
    def fake_build_provider(name: str, *, config: Any = None) -> FakeProvider:
        if name != "openai":
            raise providers.ProviderConfigurationError(f"{name} is not configured")
        return provider

    monkeypatch.setattr(providers, "build_provider", fake_build_provider)


def _token(client: TestClient, email: str = "alice@example.com") -> str:
    response = client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": "correct-horse"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup(client: TestClient) -> tuple[str, dict[str, Any], dict[str, Any]]:
    token = _token(client)
    material = client.post(
        "/api/v1/materials",
        json={"title": "Arithmetic", "source_type": "text", "text": "2 + 2 = 4"},
        headers=_headers(token),
    ).json()
    session = client.post(
        "/api/v1/sessions",
        json={"material_id": material["id"], "learning_goal": "Learn addition"},
        headers=_headers(token),
    ).json()
    return token, material, session


def test_typed_ai_results_flow_through_existing_endpoints(
    client: TestClient,
    fake_db: FakeDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider(
        [
            json.dumps(LESSON_PAYLOAD),
            json.dumps(QUIZ_PAYLOAD),
            json.dumps(EVALUATION_PAYLOAD),
        ]
    )
    _install_provider(monkeypatch, provider)
    token, material, session = _setup(client)
    session_id = session["session_id"]

    lesson_response = client.post(
        f"/api/v1/sessions/{session_id}/next",
        json={"topic": "addition"},
        headers=_headers(token),
    )
    assert lesson_response.status_code == 200, lesson_response.text
    lesson = lesson_response.json()["lesson"]
    assert lesson["title"] == "Adding numbers"
    assert lesson["check_for_understanding"] == "What is 3 + 1?"
    assert json.loads(fake_db.messages[0]["content"]) == LESSON_PAYLOAD

    quiz_response = client.post(
        f"/api/v1/sessions/{session_id}/quiz",
        json={"topic": "arithmetic", "difficulty": "easy", "count": 2},
        headers=_headers(token),
    )
    assert quiz_response.status_code == 200, quiz_response.text
    questions = quiz_response.json()["questions"]
    assert len(questions) == 2
    # The service maps correct_option_index to expected_answer so the existing
    # answer endpoint works without a database migration.
    assert questions[0]["expected_answer"] == "4"
    assert questions[0]["correct_option_index"] == 1
    assert questions[0]["rubric"] == "2 + 2 = 4."
    assert questions[0]["id"]

    answer_response = client.post(
        f"/api/v1/sessions/{session_id}/answer",
        json={"question_id": questions[0]["id"], "answer": "4"},
        headers=_headers(token),
    )
    assert answer_response.status_code == 200, answer_response.text
    evaluation = answer_response.json()
    assert evaluation["is_correct"] is True
    assert evaluation["score"] == 0.9
    assert evaluation["next_step"] == "Try a two-digit addition problem."

    progress = client.get("/api/v1/progress", headers=_headers(token)).json()
    assert len(progress) == 1
    assert progress[0]["topic"] == "arithmetic"
    assert progress[0]["mastery_score"] == 0.9


def test_invalid_ai_output_returns_502_without_persisting(
    client: TestClient,
    fake_db: FakeDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_provider(monkeypatch, FakeProvider(["not json", "still not json"]))
    token, _, session = _setup(client)

    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/next",
        json={},
        headers=_headers(token),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI engine failed to generate lesson"
    assert fake_db.messages == []


def test_provider_unavailable_returns_502(
    client: TestClient,
    fake_db: FakeDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_provider(
        monkeypatch,
        FakeProvider([providers.ProviderTransientError("provider down")]),
    )
    token, _, session = _setup(client)

    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/quiz",
        json={"topic": "arithmetic", "difficulty": "easy", "count": 2},
        headers=_headers(token),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "AI engine failed to generate quiz"


def test_database_failure_returns_safe_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_get_db():
        raise psycopg.OperationalError(
            "connection failed for postgresql://user:super-secret@example/db"
        )

    monkeypatch.setattr(learning_service, "get_db", broken_get_db)
    token = create_access_token(str(uuid.uuid4()))

    response = client.get("/api/v1/progress", headers=_headers(token))

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "super-secret" not in response.text


def test_application_starts_and_serves_openapi() -> None:
    with TestClient(app) as test_client:
        assert test_client.get("/health").json() == {"status": "OK"}
        openapi = test_client.get("/openapi.json")
        assert openapi.status_code == 200
        assert "/api/v1/sessions" in openapi.json()["paths"]
        assert test_client.get("/docs").status_code == 200
