"""LangGraph workflow coordinating prompt preparation, generation and validation.

The graph is intentionally small and deterministic:

    prepare -> generate -> validate -> (repair -> validate) -> END

Only the validation node may trigger one repair. Provider retries and provider
fallback live in ``providers.py``; the graph never loops unbounded.
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError

from app.ai_engine import prompts
from app.ai_engine.models import (
    AIOutputInvalid,
    AssistantChatResult,
    EmailPriorityResult,
    EmailSummaryResult,
    EvaluationResult,
    LessonResult,
    QuizResult,
    ReplyDraftResult,
    SecurityAnalysisResult,
    TaskExtractionResult,
    TASK_MODELS,
)
from app.ai_engine.providers import generate_structured
from app.core.config import settings

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    task: str
    inputs: dict[str, Any]
    system_prompt: str
    user_prompt: str
    schema: dict[str, Any]
    raw_output: str
    provider: str
    result: BaseModel | None
    validation_error: str | None
    repaired: bool


def _extract_json(text: str) -> Any:
    """Parse a JSON payload, tolerating Markdown fences or leading prose."""

    value = (text or "").strip()
    if not value:
        raise ValueError("empty response")

    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    start = value.find("{")
    end = value.rfind("}")
    if start != -1 and end > start:
        return json.loads(value[start : end + 1])
    raise ValueError("response is not valid JSON")


def _schema_for(task: str) -> dict[str, Any]:
    if task not in TASK_MODELS:
        raise ValueError(f"Unknown AI task: {task}")
    return TASK_MODELS[task].model_json_schema()


def _prepare_node(state: WorkflowState) -> dict[str, Any]:
    task = state["task"]
    payload = state.get("inputs", {})
    schema = _schema_for(task)

    if task == "lesson":
        system_prompt, user_prompt = prompts.build_lesson_prompts(
            material_text=str(payload.get("material_text", "")),
            topic=str(payload.get("topic") or "General"),
            student_level=str(payload.get("student_level") or "beginner"),
            learning_goal=str(payload.get("learning_goal") or ""),
            conversation_history=payload.get("conversation_history"),
            schema=schema,
            max_material_chars=settings.AI_MAX_MATERIAL_CHARS,
            max_history_messages=settings.AI_MAX_CONVERSATION_MESSAGES,
        )
    elif task == "quiz":
        system_prompt, user_prompt = prompts.build_quiz_prompts(
            material_text=str(payload.get("material_text", "")),
            topic=str(payload.get("topic") or "General"),
            difficulty=str(payload.get("difficulty") or "medium"),
            count=int(payload.get("count") or 5),
            schema=schema,
            max_material_chars=settings.AI_MAX_MATERIAL_CHARS,
        )
    elif task == "email_summary":
        system_prompt, user_prompt = prompts.build_email_summary_prompts(
            subject=str(payload.get("subject", "")),
            sender=str(payload.get("sender", "")),
            content=str(payload.get("content", "")),
            schema=schema,
        )
    elif task == "email_priority":
        system_prompt, user_prompt = prompts.build_priority_prompts(
            subject=str(payload.get("subject", "")),
            sender=str(payload.get("sender", "")),
            content=str(payload.get("content", "")),
            schema=schema,
        )
    elif task == "email_reply":
        system_prompt, user_prompt = prompts.build_reply_prompts(
            subject=str(payload.get("subject", "")),
            sender=str(payload.get("sender", "")),
            content=str(payload.get("content", "")),
            tone=str(payload.get("tone") or "professional"),
            user_notes=str(payload.get("user_notes", "")),
            schema=schema,
        )
    elif task == "email_tasks":
        system_prompt, user_prompt = prompts.build_task_extraction_prompts(
            subject=str(payload.get("subject", "")),
            sender=str(payload.get("sender", "")),
            content=str(payload.get("content", "")),
            schema=schema,
        )
    elif task == "email_security":
        system_prompt, user_prompt = prompts.build_security_analysis_prompts(
            subject=str(payload.get("subject", "")),
            sender=str(payload.get("sender", "")),
            sender_email=str(payload.get("sender_email", "")),
            content=str(payload.get("content", "")),
            schema=schema,
        )
    elif task == "assistant_chat":
        system_prompt, user_prompt = prompts.build_assistant_chat_prompts(
            query=str(payload.get("query", "")),
            context_text=str(payload.get("context_text", "")),
            schema=schema,
        )
    else:
        system_prompt, user_prompt = prompts.build_evaluation_prompts(
            question=str(payload.get("question", "")),
            expected_answer=str(payload.get("expected_answer", "")),
            student_answer=str(payload.get("student_answer", "")),
            rubric=str(payload.get("rubric", "")),
            schema=schema,
        )

    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "schema": schema,
        "result": None,
        "validation_error": None,
        "repaired": False,
    }


async def _generate_node(state: WorkflowState) -> dict[str, Any]:
    response = await generate_structured(
        system_prompt=state["system_prompt"],
        user_prompt=state["user_prompt"],
        json_schema=state["schema"],
    )
    return {"raw_output": response.text, "provider": response.provider}


def _validate_node(state: WorkflowState) -> dict[str, Any]:
    model = TASK_MODELS[state["task"]]
    try:
        parsed = _extract_json(state.get("raw_output", ""))
        result = model.model_validate(parsed)
    except (ValueError, ValidationError) as exc:
        # The message is fed back to the model for repair; it is never logged
        # with raw student content and never returned to the API client.
        return {"result": None, "validation_error": str(exc)[:4_000]}
    return {"result": result, "validation_error": None}


async def _repair_node(state: WorkflowState) -> dict[str, Any]:
    system_prompt, user_prompt = prompts.build_repair_prompts(
        original_user_prompt=state.get("user_prompt", ""),
        invalid_output=state.get("raw_output", ""),
        validation_error=state.get("validation_error", ""),
        schema=state["schema"],
    )
    response = await generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_schema=state["schema"],
    )
    return {
        "raw_output": response.text,
        "provider": response.provider,
        "repaired": True,
    }


def _route_after_validation(state: WorkflowState) -> str:
    if state.get("result") is not None:
        return "end"
    if state.get("repaired"):
        return "end"
    return "repair"


def _build_graph():
    workflow = StateGraph(WorkflowState)
    workflow.add_node("prepare", _prepare_node)
    workflow.add_node("generate", _generate_node)
    workflow.add_node("validate", _validate_node)
    workflow.add_node("repair", _repair_node)

    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "generate")
    workflow.add_edge("generate", "validate")
    workflow.add_conditional_edges(
        "validate",
        _route_after_validation,
        {"repair": "repair", "end": END},
    )
    workflow.add_edge("repair", "validate")
    return workflow.compile()


_GRAPH = _build_graph()


async def run_workflow(task: str, payload: dict[str, Any]) -> BaseModel:
    """Run one task and return its validated Pydantic result."""

    if task not in TASK_MODELS:
        raise ValueError(f"Unknown AI task: {task}")

    state = await _GRAPH.ainvoke({"task": task, "inputs": payload})
    result = state.get("result")
    if result is None:
        logger.warning("AI task %s returned invalid output after repair", task)
        raise AIOutputInvalid("AI response did not match the required schema")
    if not isinstance(result, TASK_MODELS[task]):
        raise AIOutputInvalid("AI response has an unexpected result type")
    return result


async def run_lesson(
    *,
    material_text: str,
    topic: str | None = None,
    student_level: str = "beginner",
    learning_goal: str | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
) -> LessonResult:
    result = await run_workflow(
        "lesson",
        {
            "material_text": material_text,
            "topic": topic,
            "student_level": student_level,
            "learning_goal": learning_goal,
            "conversation_history": conversation_history or [],
        },
    )
    assert isinstance(result, LessonResult)
    return result


async def run_quiz(
    *,
    material_text: str,
    topic: str,
    difficulty: str,
    count: int,
) -> QuizResult:
    result = await run_workflow(
        "quiz",
        {
            "material_text": material_text,
            "topic": topic,
            "difficulty": difficulty,
            "count": count,
        },
    )
    assert isinstance(result, QuizResult)
    return result


async def run_evaluation(
    *,
    question: str,
    expected_answer: str,
    student_answer: str,
    rubric: str,
) -> EvaluationResult:
    result = await run_workflow(
        "evaluation",
        {
            "question": question,
            "expected_answer": expected_answer,
            "student_answer": student_answer,
            "rubric": rubric,
        },
    )
    assert isinstance(result, EvaluationResult)
    return result


async def run_email_summary(
    *,
    subject: str,
    sender: str,
    content: str,
) -> EmailSummaryResult:
    result = await run_workflow(
        "email_summary",
        {"subject": subject, "sender": sender, "content": content},
    )
    return result  # type: ignore


async def run_email_priority(
    *,
    subject: str,
    sender: str,
    content: str,
) -> EmailPriorityResult:
    result = await run_workflow(
        "email_priority",
        {"subject": subject, "sender": sender, "content": content},
    )
    return result  # type: ignore


async def run_email_reply(
    *,
    subject: str,
    sender: str,
    content: str,
    tone: str = "professional",
    user_notes: str = "",
) -> ReplyDraftResult:
    result = await run_workflow(
        "email_reply",
        {
            "subject": subject,
            "sender": sender,
            "content": content,
            "tone": tone,
            "user_notes": user_notes,
        },
    )
    return result  # type: ignore


async def run_task_extraction(
    *,
    subject: str,
    sender: str,
    content: str,
) -> TaskExtractionResult:
    result = await run_workflow(
        "email_tasks",
        {"subject": subject, "sender": sender, "content": content},
    )
    return result  # type: ignore


async def run_security_analysis(
    *,
    subject: str,
    sender: str,
    sender_email: str,
    content: str,
) -> SecurityAnalysisResult:
    result = await run_workflow(
        "email_security",
        {
            "subject": subject,
            "sender": sender,
            "sender_email": sender_email,
            "content": content,
        },
    )
    return result  # type: ignore


async def run_assistant_chat(
    *,
    query: str,
    context_text: str,
) -> AssistantChatResult:
    result = await run_workflow(
        "assistant_chat",
        {"query": query, "context_text": context_text},
    )
    return result  # type: ignore

