"""Business logic for authentication, materials, sessions, quizzes and progress.

Route handlers stay thin; every SQL statement, ownership check and AI engine
call lives here.
"""

from __future__ import annotations

import json
import logging
import math
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg
from fastapi import HTTPException, status
from psycopg.types.json import Jsonb

from app.ai_engine import evaluate_answer, generate_lesson, generate_quiz
from app.ai_engine.models import model_payload
from app.core.security import create_access_token, hash_password, verify_password
from app.db.client import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def register_or_login(email: str, password: str) -> str:
    """Auto-register a new user or verify an existing one, returning a JWT."""

    email = email.strip().lower()
    display_name = email.split("@", 1)[0]

    with get_db() as cur:
        # ``ON CONFLICT DO NOTHING`` keeps concurrent registrations safe: one
        # request creates the user, the other falls through to verification.
        cur.execute(
            """
            INSERT INTO users (email, password_hash, display_name)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (email, hash_password(password), display_name),
        )
        created_user = cur.fetchone()
        if created_user is not None:
            return create_access_token(str(created_user["id"]))

        cur.execute(
            "SELECT id, password_hash FROM users WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create or load user",
        )
    if not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return create_access_token(str(user["id"]))


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


async def create_material(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Persist a learning material for the authenticated user."""

    extracted_text = data.get("text") or data.get("storage_path") or ""
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO learning_materials (user_id, title, source_type, extracted_text)
            VALUES (%s, %s, %s, %s)
            RETURNING id, user_id, title, source_type, extracted_text, created_at
            """,
            (user_id, data["title"], data["source_type"], extracted_text),
        )
        material = cur.fetchone()

    if material is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create material",
        )
    return material


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def _get_session(cur: psycopg.Cursor, user_id: str, session_id: str) -> dict[str, Any]:
    """Load a session only when it belongs to ``user_id``."""

    cur.execute(
        "SELECT * FROM learning_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    session = cur.fetchone()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session


def _get_material_text(cur: psycopg.Cursor, material_id: Any) -> str:
    cur.execute(
        "SELECT extracted_text FROM learning_materials WHERE id = %s",
        (material_id,),
    )
    material = cur.fetchone()
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )
    return material["extracted_text"] or ""


async def create_session(
    user_id: str,
    material_id: str,
    learning_goal: str | None = None,
) -> dict[str, Any]:
    """Create an active learning session after verifying material ownership."""

    with get_db() as cur:
        cur.execute(
            "SELECT id FROM learning_materials WHERE id = %s AND user_id = %s",
            (material_id, user_id),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material not found",
            )

        cur.execute(
            """
            INSERT INTO learning_sessions (user_id, material_id, status, current_topic)
            VALUES (%s, %s, 'active', %s)
            RETURNING id, status, material_id, current_topic
            """,
            (user_id, material_id, learning_goal),
        )
        session = cur.fetchone()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create session",
        )
    return session


async def get_session_details(user_id: str, session_id: str) -> dict[str, Any]:
    """Return a session and its messages in chronological order."""

    with get_db() as cur:
        session = _get_session(cur, user_id, session_id)
        cur.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        )
        messages = cur.fetchall()

    return {"session": session, "messages": messages}


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> str:
    """Serialize arbitrary AI output into text for the ``messages.content`` column."""

    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


async def generate_next_lesson(
    user_id: str,
    session_id: str,
    topic: str | None = None,
) -> dict[str, Any]:
    """Generate and persist the next assistant lesson message."""

    with get_db() as cur:
        session = _get_session(cur, user_id, session_id)
        material_text = _get_material_text(cur, session["material_id"])
        cur.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        )
        conversation_history = [
            {"role": row["role"], "content": row["content"]}
            for row in cur.fetchall()
        ]

    effective_topic = topic or session.get("current_topic") or "General"
    learning_goal = session.get("current_topic") or "Continue learning"

    try:
        lesson = await generate_lesson(
            material_text=material_text,
            topic=effective_topic,
            student_level="beginner",
            learning_goal=learning_goal,
            conversation_history=conversation_history,
        )
    except Exception as exc:  # noqa: BLE001 - external engine boundary
        logger.exception("generate_lesson failed for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI engine failed to generate lesson",
        ) from exc

    # The AI engine returns ``LessonResult``; older/mocked engines may still
    # return a plain string. Normalise both into JSON-compatible data.
    lesson_payload = model_payload(lesson)

    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO messages (session_id, role, content)
            VALUES (%s, 'assistant', %s)
            RETURNING id
            """,
            (session_id, _jsonable(lesson_payload)),
        )
        if topic:
            cur.execute(
                """
                UPDATE learning_sessions
                SET current_topic = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (topic, session_id, user_id),
            )

    return {"lesson": lesson_payload}


# ---------------------------------------------------------------------------
# Quizzes / answers
# ---------------------------------------------------------------------------


def _normalize_question(raw: Any, topic: str, difficulty: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        question = dict(raw)
    else:
        question = {"question": str(raw)}
    question.setdefault("topic", topic)
    question.setdefault("difficulty", difficulty)

    # The typed AI engine returns MCQ data with ``correct_option_index`` and
    # no redundant ``expected_answer``. Persist both so the existing answer
    # evaluation endpoint keeps working without a schema migration.
    options = question.get("options")
    option_index = question.get("correct_option_index")
    if (
        "expected_answer" not in question
        and isinstance(options, list)
        and isinstance(option_index, int)
        and 0 <= option_index < len(options)
    ):
        question["expected_answer"] = options[option_index]

    if not question.get("rubric"):
        question["rubric"] = question.get("explanation") or ""

    return question


def _coerce_quiz_questions(raw: Any) -> list[Any]:
    """Accept ``QuizResult``, a list, or a legacy ``{"questions": [...]}`` dict."""

    payload = model_payload(raw)
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        payload = payload["questions"]
    if isinstance(payload, list):
        return payload
    return []


async def generate_quiz_for_session(
    user_id: str,
    session_id: str,
    topic: str,
    difficulty: str,
    count: int,
) -> dict[str, Any]:
    """Generate quiz questions with the AI engine and persist them."""

    with get_db() as cur:
        session = _get_session(cur, user_id, session_id)
        material_text = _get_material_text(cur, session["material_id"])

    try:
        generated = await generate_quiz(
            material_text=material_text,
            topic=topic,
            difficulty=difficulty,
            count=count,
        )
    except Exception as exc:  # noqa: BLE001 - external engine boundary
        logger.exception("generate_quiz failed for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI engine failed to generate quiz",
        ) from exc

    raw_questions = _coerce_quiz_questions(generated)
    if not raw_questions:
        logger.error("generate_quiz returned an invalid payload for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI engine returned an invalid quiz",
        )

    questions = [_normalize_question(item, topic, difficulty) for item in raw_questions]

    saved_questions: list[dict[str, Any]] = []
    with get_db() as cur:
        for question in questions:
            cur.execute(
                """
                INSERT INTO quiz_questions (session_id, question_json)
                VALUES (%s, %s)
                RETURNING id, created_at
                """,
                (session_id, Jsonb(question)),
            )
            row = cur.fetchone()
            saved_questions.append({**question, "id": str(row["id"])})

        cur.execute(
            """
            UPDATE learning_sessions
            SET current_topic = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            """,
            (topic, session_id, user_id),
        )

    return {"topic": topic, "difficulty": difficulty, "questions": saved_questions}


def _normalize_score(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        score = float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0
    if not math.isfinite(score):
        return 0.0
    return max(0.0, min(1.0, round(score, 4)))


def _load_question_payload(question_json: Any) -> dict[str, Any]:
    if isinstance(question_json, dict):
        return question_json
    if isinstance(question_json, str):
        try:
            parsed = json.loads(question_json)
        except json.JSONDecodeError:
            return {"question": question_json}
        return parsed if isinstance(parsed, dict) else {"question": question_json}
    return {}


async def process_answer(
    user_id: str,
    session_id: str,
    question_id: str,
    answer: str,
) -> dict[str, Any]:
    """Evaluate an answer, store the attempt and update mastery progress."""

    with get_db() as cur:
        session = _get_session(cur, user_id, session_id)
        cur.execute(
            """
            SELECT question_json
            FROM quiz_questions
            WHERE id = %s AND session_id = %s
            """,
            (question_id, session_id),
        )
        question_row = cur.fetchone()

    if question_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    question_json = _load_question_payload(question_row["question_json"])
    question_text = (
        question_json.get("question")
        or question_json.get("text")
        or question_json.get("prompt")
        or ""
    )
    expected_answer = (
        question_json.get("expected_answer")
        or question_json.get("expected")
        or question_json.get("answer")
        or ""
    )
    if not isinstance(question_text, str):
        question_text = str(question_text)
    if not isinstance(expected_answer, str):
        expected_answer = str(expected_answer)
    rubric = question_json.get("rubric") or "{}"
    if not isinstance(rubric, str):
        rubric = json.dumps(rubric, ensure_ascii=False, default=str)
    topic = question_json.get("topic") or session.get("current_topic") or "General"

    try:
        evaluation = await evaluate_answer(
            question=question_text,
            expected_answer=expected_answer,
            student_answer=answer,
            rubric=rubric,
        )
    except Exception as exc:  # noqa: BLE001 - external engine boundary
        logger.exception("evaluate_answer failed for question %s", question_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI engine failed to evaluate answer",
        ) from exc

    evaluation = model_payload(evaluation)
    if not isinstance(evaluation, dict):
        logger.error("evaluate_answer returned an invalid payload for question %s", question_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI engine returned an invalid evaluation",
        )

    score = _normalize_score(evaluation.get("score", evaluation.get("is_correct", 0.0)))
    feedback = evaluation.get("feedback")
    if feedback is not None and not isinstance(feedback, str):
        feedback = json.dumps(feedback, ensure_ascii=False, default=str)

    next_step = evaluation.get("next_step")
    if next_step is not None and not isinstance(next_step, str):
        next_step = json.dumps(next_step, ensure_ascii=False, default=str)

    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO quiz_attempts (question_id, user_id, answer, score, feedback)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (question_id, user_id, answer, score, feedback),
        )
        # Exponential moving average keeps mastery responsive without needing
        # an extra attempt counter column.
        cur.execute(
            """
            INSERT INTO progress (user_id, material_id, topic, mastery_score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, material_id, topic) DO UPDATE
            SET mastery_score = ROUND(
                    ((progress.mastery_score * 0.7) + (EXCLUDED.mastery_score * 0.3))::numeric,
                    4
                ),
                updated_at = NOW()
            RETURNING id
            """,
            (user_id, session["material_id"], topic, score),
        )

    result = dict(evaluation)
    result["score"] = score
    if feedback is not None:
        result["feedback"] = feedback
    if next_step is not None:
        result["next_step"] = next_step
    return result


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


async def get_user_progress(
    user_id: str,
    material_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return progress rows belonging to the authenticated user."""

    with get_db() as cur:
        if material_id:
            cur.execute(
                """
                SELECT id, user_id, material_id, topic, mastery_score, updated_at
                FROM progress
                WHERE user_id = %s AND material_id = %s
                ORDER BY updated_at DESC, topic ASC
                """,
                (user_id, material_id),
            )
        else:
            cur.execute(
                """
                SELECT id, user_id, material_id, topic, mastery_score, updated_at
                FROM progress
                WHERE user_id = %s
                ORDER BY updated_at DESC, topic ASC
                """,
                (user_id,),
            )
        rows = cur.fetchall()

    for row in rows:
        row["mastery_score"] = float(row["mastery_score"])
    return rows
