"""Public AI-engine contract used by ``app.services.learning_service``.

The engine is deliberately independent of FastAPI and the database. It returns
validated Pydantic models and raises typed errors:

- ``AIProviderUnavailable``: no configured provider could serve the request.
- ``AIOutputInvalid``: provider output failed validation after one repair.

The original mock implementation in Person 1's project returned plain strings
and lists. These functions keep accepting the same keyword calls, while the
service layer normalises the richer typed results before persistence.
"""

from __future__ import annotations

from typing import Any

from app.ai_engine.graph import run_evaluation, run_lesson, run_quiz
from app.ai_engine.models import (
    AIEngineError,
    AIOutputInvalid,
    AIProviderUnavailable,
    EvaluationResult,
    LessonResult,
    QuizQuestion,
    QuizResult,
)


async def generate_lesson(
    *,
    material_text: str,
    topic: str | None = None,
    student_level: str = "beginner",
    learning_goal: str | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
) -> LessonResult:
    """Generate the next structured lesson for a learning session."""

    return await run_lesson(
        material_text=material_text,
        topic=topic,
        student_level=student_level,
        learning_goal=learning_goal,
        conversation_history=conversation_history,
    )


async def generate_quiz(
    *,
    material_text: str,
    topic: str,
    difficulty: str,
    count: int,
) -> QuizResult:
    """Generate a structured multiple-choice quiz."""

    return await run_quiz(
        material_text=material_text,
        topic=topic,
        difficulty=difficulty,
        count=count,
    )


async def evaluate_answer(
    *,
    question: str,
    expected_answer: str,
    student_answer: str,
    rubric: str = "",
) -> EvaluationResult:
    """Evaluate a student's answer and suggest the next learning step."""

    return await run_evaluation(
        question=question,
        expected_answer=expected_answer,
        student_answer=student_answer,
        rubric=rubric,
    )


__all__ = [
    "AIEngineError",
    "AIOutputInvalid",
    "AIProviderUnavailable",
    "EvaluationResult",
    "LessonResult",
    "QuizQuestion",
    "QuizResult",
    "evaluate_answer",
    "generate_lesson",
    "generate_quiz",
]
