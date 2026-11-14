"""API tests for Person 1's learning work package.

The suite uses an in-memory fake cursor so it can exercise the real routes and
service logic without a live Neon/PostgreSQL connection. AI engine calls are
monkeypatched per test.
"""

from __future__ import annotations

import itertools
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

# Settings are instantiated at import time; provide safe fallbacks so the test
# suite also runs in a checkout without a local .env file. The fake database
# means these values are never used to open a connection.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import learning_service  # noqa: E402


# ---------------------------------------------------------------------------
# In-memory database double
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeDatabase:
    """Small state store implementing only the SQL used by the service layer."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.materials: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.messages: list[dict[str, Any]] = []
        self.questions: dict[str, dict[str, Any]] = {}
        self.attempts: list[dict[str, Any]] = []
        self.progress: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._ids = itertools.count(1)

    def new_id(self) -> str:
        # Include the counter so generated UUIDs are easy to reason about.
        return str(uuid.UUID(int=next(self._ids)))

    def execute(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        query = " ".join(sql.split()).lower()
        params = tuple(params or ())

        # -- auth ---------------------------------------------------------
        if query.startswith("insert into users"):
            email, password_hash, display_name = params
            if email in self.users:
                return []
            user_id = self.new_id()
            self.users[email] = {
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "display_name": display_name,
                "created_at": _now(),
            }
            return [{"id": user_id}]

        if query.startswith("select id, password_hash from users"):
            user = self.users.get(params[0])
            if user is None:
                return []
            return [{"id": user["id"], "password_hash": user["password_hash"]}]

        # -- materials ----------------------------------------------------
        if query.startswith("insert into learning_materials"):
            user_id, title, source_type, extracted_text = params
            material_id = self.new_id()
            material = {
                "id": material_id,
                "user_id": user_id,
                "title": title,
                "source_type": source_type,
                "extracted_text": extracted_text,
                "created_at": _now(),
            }
            self.materials[material_id] = material
            return [dict(material)]

        if query.startswith("select id from learning_materials"):
            material_id, user_id = params
            material = self.materials.get(str(material_id))
            if material is None or str(material["user_id"]) != str(user_id):
                return []
            return [{"id": material["id"]}]

        if query.startswith("select extracted_text from learning_materials"):
            material = self.materials.get(str(params[0]))
            if material is None:
                return []
            return [{"extracted_text": material["extracted_text"]}]

        # -- sessions -----------------------------------------------------
        if query.startswith("insert into learning_sessions"):
            user_id, material_id, current_topic = params
            session_id = self.new_id()
            timestamp = _now()
            session = {
                "id": session_id,
                "user_id": user_id,
                "material_id": material_id,
                "status": "active",
                "current_topic": current_topic,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            self.sessions[session_id] = session
            return [
                {
                    "id": session_id,
                    "status": "active",
                    "material_id": material_id,
                    "current_topic": current_topic,
                }
            ]

        if query.startswith("select * from learning_sessions where id ="):
            session = self.sessions.get(str(params[0]))
            if session is None or str(session["user_id"]) != str(params[1]):
                return []
            return [dict(session)]

        if query.startswith("update learning_sessions"):
            topic, session_id, user_id = params
            session = self.sessions.get(str(session_id))
            if session is None or str(session["user_id"]) != str(user_id):
                return []
            session["current_topic"] = topic
            session["updated_at"] = _now()
            return []

        # -- messages -----------------------------------------------------
        if query.startswith("insert into messages"):
            session_id, content = params
            message = {
                "id": self.new_id(),
                "session_id": session_id,
                "role": "assistant",
                "content": content,
                "created_at": _now(),
            }
            self.messages.append(message)
            return [{"id": message["id"]}]

        if query.startswith("select role, content from messages"):
            session_id = str(params[0])
            return [
                {"role": m["role"], "content": m["content"]}
                for m in self.messages
                if str(m["session_id"]) == session_id
            ]

        if query.startswith("select id, session_id, role, content, created_at from messages"):
            session_id = str(params[0])
            return [
                dict(m) for m in self.messages if str(m["session_id"]) == session_id
            ]

        # -- quiz questions ----------------------------------------------
        if query.startswith("insert into quiz_questions"):
            session_id, payload = params
            question_json = getattr(payload, "obj", payload)
            question_id = self.new_id()
            question = {
                "id": question_id,
                "session_id": session_id,
                "question_json": question_json,
                "created_at": _now(),
            }
            self.questions[question_id] = question
            return [{"id": question_id, "created_at": question["created_at"]}]

        if query.startswith("select question_json from quiz_questions"):
            question_id, session_id = params
            question = self.questions.get(str(question_id))
            if question is None or str(question["session_id"]) != str(session_id):
                return []
            return [{"question_json": question["question_json"]}]

        # -- quiz attempts ------------------------------------------------
        if query.startswith("insert into quiz_attempts"):
            question_id, user_id, answer, score, feedback = params
            attempt = {
                "id": self.new_id(),
                "question_id": question_id,
                "user_id": user_id,
                "answer": answer,
                "score": score,
                "feedback": feedback,
                "created_at": _now(),
            }
            self.attempts.append(attempt)
            return [{"id": attempt["id"]}]

        # -- progress -----------------------------------------------------
        if query.startswith("insert into progress"):
            user_id, material_id, topic, score = params
            key = (str(user_id), str(material_id), topic)
            existing = self.progress.get(key)
            if existing is None:
                mastery = Decimal(str(score))
                row = {
                    "id": self.new_id(),
                    "user_id": user_id,
                    "material_id": material_id,
                    "topic": topic,
                    "mastery_score": mastery,
                    "updated_at": _now(),
                }
            else:
                mastery = (
                    Decimal(str(existing["mastery_score"])) * Decimal("0.7")
                    + Decimal(str(score)) * Decimal("0.3")
                ).quantize(Decimal("0.0001"))
                row = {
                    **existing,
                    "mastery_score": mastery,
                    "updated_at": _now(),
                }
            self.progress[key] = row
            return [{"id": row["id"]}]

        if query.startswith(
            "select id, user_id, material_id, topic, mastery_score, updated_at from progress"
        ):
            user_id = str(params[0])
            material_filter = str(params[1]) if len(params) > 1 else None
            rows = [
                dict(row)
                for row in self.progress.values()
                if str(row["user_id"]) == user_id
                and (
                    material_filter is None
                    or str(row["material_id"]) == material_filter
                )
            ]
            return sorted(rows, key=lambda row: row["updated_at"], reverse=True)

        raise AssertionError(f"Unhandled SQL in test fake: {query}")


class FakeCursor:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self._rows: list[dict[str, Any]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._rows = self.database.execute(sql, params or ())

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


@pytest.fixture(autouse=True)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _token(client: TestClient, email: str, password: str = "correct-horse") -> str:
    response = client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_material(client: TestClient, token: str, text: str = "2 + 2 = 4") -> dict:
    response = client.post(
        "/api/v1/materials",
        json={"title": "Arithmetic", "source_type": "text", "text": text},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_session(client: TestClient, token: str, material_id: str) -> dict:
    response = client.post(
        "/api/v1/sessions",
        json={"material_id": material_id, "learning_goal": "Learn basic arithmetic"},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _setup_session(client: TestClient, email: str = "alice@example.com") -> tuple[str, dict, dict]:
    token = _token(client, email)
    material = _create_material(client, token)
    session = _create_session(client, token, material["id"])
    return token, material, session


# ---------------------------------------------------------------------------
# Health / auth
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/progress", None),
        ("post", "/api/v1/materials", {"title": "x", "source_type": "text", "text": "y"}),
        ("post", "/api/v1/sessions", {"material_id": str(uuid.uuid4())}),
    ],
)
def test_protected_routes_reject_missing_token(
    client: TestClient,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    request_kwargs = {"json": payload} if payload is not None else {}
    response = getattr(client, method)(path, **request_kwargs)
    assert response.status_code in (401, 403)
    assert response.status_code == 401


def test_protected_routes_reject_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/progress",
        headers={"Authorization": "Bearer definitely-not-a-jwt"},
    )
    assert response.status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/api/v1/progress", headers=_headers(expired))
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_register_then_login_and_password_hashing(
    client: TestClient,
    fake_db: FakeDatabase,
) -> None:
    token = _token(client, "Alice@Example.com")
    assert token

    response = client.post(
        "/api/v1/auth/token",
        json={"email": "alice@example.com", "password": "correct-horse"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    wrong_password = client.post(
        "/api/v1/auth/token",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert wrong_password.status_code == 401

    assert "alice@example.com" in fake_db.users
    assert fake_db.users["alice@example.com"]["password_hash"] != "correct-horse"


# ---------------------------------------------------------------------------
# Materials / sessions
# ---------------------------------------------------------------------------


def test_create_material_and_session(client: TestClient) -> None:
    token = _token(client, "alice@example.com")

    material_response = client.post(
        "/api/v1/materials",
        json={
            "title": "Arithmetic basics",
            "source_type": "text",
            "text": "Two plus two equals four.",
        },
        headers=_headers(token),
    )
    assert material_response.status_code == 200
    material = material_response.json()
    assert material["title"] == "Arithmetic basics"
    assert material["source_type"] == "text"
    assert material["extracted_text"] == "Two plus two equals four."

    session_response = client.post(
        "/api/v1/sessions",
        json={"material_id": material["id"], "learning_goal": "Master addition"},
        headers=_headers(token),
    )
    assert session_response.status_code == 200
    session = session_response.json()
    assert session["status"] == "active"
    assert uuid.UUID(session["session_id"])

    details_response = client.get(
        f"/api/v1/sessions/{session['session_id']}",
        headers=_headers(token),
    )
    assert details_response.status_code == 200
    details = details_response.json()
    assert details["session"]["id"] == session["session_id"]
    assert details["session"]["current_topic"] == "Master addition"
    assert details["messages"] == []


def test_material_requires_text_or_storage_path(client: TestClient) -> None:
    token = _token(client, "alice@example.com")
    response = client.post(
        "/api/v1/materials",
        json={"title": "Empty", "source_type": "text"},
        headers=_headers(token),
    )
    assert response.status_code == 422


def test_material_accepts_storage_path(client: TestClient) -> None:
    token = _token(client, "alice@example.com")
    response = client.post(
        "/api/v1/materials",
        json={
            "title": "PDF notes",
            "source_type": "pdf",
            "storage_path": "s3://bucket/notes.pdf",
        },
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["extracted_text"] == "s3://bucket/notes.pdf"


def test_session_ownership_is_enforced(client: TestClient) -> None:
    alice_token, alice_material, alice_session = _setup_session(client, "alice@example.com")
    bob_token = _token(client, "bob@example.com")

    assert (
        client.get(
            f"/api/v1/sessions/{alice_session['session_id']}",
            headers=_headers(bob_token),
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/sessions",
            json={"material_id": alice_material["id"]},
            headers=_headers(bob_token),
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/sessions/{alice_session['session_id']}/next",
            json={},
            headers=_headers(bob_token),
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Lessons / AI engine boundaries
# ---------------------------------------------------------------------------


def test_next_lesson_calls_ai_and_persists_message(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, material, session = _setup_session(client)
    captured: dict[str, Any] = {}

    async def fake_generate_lesson(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "Lesson: solve x + 2 = 4"

    monkeypatch.setattr(learning_service, "generate_lesson", fake_generate_lesson)

    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/next",
        json={"topic": "linear equations"},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"lesson": "Lesson: solve x + 2 = 4"}

    assert captured["material_text"] == material["extracted_text"]
    assert captured["topic"] == "linear equations"
    assert captured["student_level"] == "beginner"
    assert captured["learning_goal"] == "Learn basic arithmetic"
    assert captured["conversation_history"] == []

    details = client.get(
        f"/api/v1/sessions/{session['session_id']}",
        headers=_headers(token),
    ).json()
    assert len(details["messages"]) == 1
    assert details["messages"][0]["role"] == "assistant"
    assert details["messages"][0]["content"] == "Lesson: solve x + 2 = 4"
    assert details["session"]["current_topic"] == "linear equations"

    second = client.post(
        f"/api/v1/sessions/{session['session_id']}/next",
        json={},
        headers=_headers(token),
    )
    assert second.status_code == 200
    assert len(captured["conversation_history"]) == 1
    assert captured["conversation_history"][0]["role"] == "assistant"


def test_next_lesson_ai_failure_returns_502(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, _, session = _setup_session(client)

    async def failing_lesson(**kwargs: Any) -> str:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(learning_service, "generate_lesson", failing_lesson)

    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/next",
        json={},
        headers=_headers(token),
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "AI engine failed to generate lesson"


# ---------------------------------------------------------------------------
# Quizzes / answers / progress
# ---------------------------------------------------------------------------


def test_quiz_answer_updates_progress(
    client: TestClient,
    fake_db: FakeDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, material, session = _setup_session(client)
    session_id = session["session_id"]

    async def fake_generate_quiz(**kwargs: Any) -> list[dict[str, Any]]:
        assert kwargs["topic"] == "arithmetic"
        assert kwargs["difficulty"] == "easy"
        assert kwargs["count"] == 2
        return [
            {
                "question": "What is 2 + 2?",
                "expected_answer": "4",
                "options": ["3", "4", "5"],
                "rubric": "One point for 4.",
            },
            {
                "question": "What is 3 + 1?",
                "expected_answer": "4",
                "options": ["2", "4", "6"],
            },
        ]

    monkeypatch.setattr(learning_service, "generate_quiz", fake_generate_quiz)

    quiz_response = client.post(
        f"/api/v1/sessions/{session_id}/quiz",
        json={"topic": "arithmetic", "difficulty": "easy", "count": 2},
        headers=_headers(token),
    )
    assert quiz_response.status_code == 200, quiz_response.text
    quiz = quiz_response.json()
    assert quiz["topic"] == "arithmetic"
    assert quiz["difficulty"] == "easy"
    assert len(quiz["questions"]) == 2
    question_id = quiz["questions"][0]["id"]
    assert len(fake_db.questions) == 2

    async def fake_evaluate_answer(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["question"] == "What is 2 + 2?"
        assert kwargs["expected_answer"] == "4"
        assert kwargs["student_answer"] == "4"
        assert kwargs["rubric"] == "One point for 4."
        return {
            "is_correct": True,
            "score": 0.9,
            "feedback": "Nice work",
            "next_step": "Try a harder question",
        }

    monkeypatch.setattr(learning_service, "evaluate_answer", fake_evaluate_answer)

    answer_response = client.post(
        f"/api/v1/sessions/{session_id}/answer",
        json={"question_id": question_id, "answer": "4"},
        headers=_headers(token),
    )
    assert answer_response.status_code == 200, answer_response.text
    evaluation = answer_response.json()
    assert evaluation["is_correct"] is True
    assert evaluation["score"] == 0.9
    assert evaluation["feedback"] == "Nice work"
    assert len(fake_db.attempts) == 1
    assert fake_db.attempts[0]["question_id"] == question_id

    progress_response = client.get("/api/v1/progress", headers=_headers(token))
    assert progress_response.status_code == 200
    progress = progress_response.json()
    assert len(progress) == 1
    assert progress[0]["material_id"] == material["id"]
    assert progress[0]["topic"] == "arithmetic"
    assert progress[0]["mastery_score"] == 0.9

    filtered = client.get(
        "/api/v1/progress",
        params={"material_id": material["id"]},
        headers=_headers(token),
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    other_material = client.get(
        "/api/v1/progress",
        params={"material_id": str(uuid.uuid4())},
        headers=_headers(token),
    )
    assert other_material.status_code == 200
    assert other_material.json() == []


def test_progress_is_scoped_to_current_user(client: TestClient) -> None:
    alice_token, alice_material, _ = _setup_session(client, "alice@example.com")
    bob_token = _token(client, "bob@example.com")

    response = client.get("/api/v1/progress", headers=_headers(bob_token))
    assert response.status_code == 200
    assert response.json() == []
    assert alice_material["id"]

    # Alice's rows never leak through Bob's token, even with her material id.
    filtered = client.get(
        "/api/v1/progress",
        params={"material_id": alice_material["id"]},
        headers=_headers(bob_token),
    )
    assert filtered.status_code == 200
    assert filtered.json() == []


def test_question_ownership_is_enforced(
    client: TestClient,
    fake_db: FakeDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alice_token, _, alice_session = _setup_session(client, "alice@example.com")

    async def fake_generate_quiz(**kwargs: Any) -> list[dict[str, Any]]:
        return [{"question": "What is 2 + 2?", "expected_answer": "4"}]

    monkeypatch.setattr(learning_service, "generate_quiz", fake_generate_quiz)

    quiz = client.post(
        f"/api/v1/sessions/{alice_session['session_id']}/quiz",
        json={"topic": "arithmetic", "difficulty": "easy", "count": 1},
        headers=_headers(alice_token),
    ).json()
    question_id = quiz["questions"][0]["id"]

    bob_token = _token(client, "bob@example.com")

    async def should_not_be_called(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("evaluate_answer must not be called for another user")

    monkeypatch.setattr(learning_service, "evaluate_answer", should_not_be_called)

    response = client.post(
        f"/api/v1/sessions/{alice_session['session_id']}/answer",
        json={"question_id": question_id, "answer": "4"},
        headers=_headers(bob_token),
    )
    assert response.status_code == 404
    assert fake_db.attempts == []


def test_quiz_ai_failure_returns_502(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, _, session = _setup_session(client)

    async def failing_quiz(**kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(learning_service, "generate_quiz", failing_quiz)

    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/quiz",
        json={"topic": "arithmetic", "difficulty": "easy", "count": 3},
        headers=_headers(token),
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "AI engine failed to generate quiz"


def test_answer_ai_failure_returns_502(
    client: TestClient,
    fake_db: FakeDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, _, session = _setup_session(client)

    async def fake_generate_quiz(**kwargs: Any) -> list[dict[str, Any]]:
        return [{"question": "What is 2 + 2?", "expected_answer": "4"}]

    monkeypatch.setattr(learning_service, "generate_quiz", fake_generate_quiz)

    quiz = client.post(
        f"/api/v1/sessions/{session['session_id']}/quiz",
        json={"topic": "arithmetic", "difficulty": "easy", "count": 1},
        headers=_headers(token),
    ).json()

    async def failing_evaluation(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(learning_service, "evaluate_answer", failing_evaluation)

    response = client.post(
        f"/api/v1/sessions/{session['session_id']}/answer",
        json={"question_id": quiz["questions"][0]["id"], "answer": "4"},
        headers=_headers(token),
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "AI engine failed to evaluate answer"
    assert fake_db.attempts == []
