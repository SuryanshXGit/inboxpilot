"""Public API routes for the learning work package."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query

from app.core.security import get_current_user_id
from app.schemas.learning import (
    AnswerRequest,
    AuthTokenRequest,
    EvaluationResponse,
    LessonResponse,
    MaterialCreate,
    MaterialResponse,
    ProgressResponse,
    QuizRequest,
    QuizResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionNextRequest,
    SessionSummaryResponse,
    TokenResponse,
)
from app.services import learning_service

router = APIRouter(prefix="/api/v1", tags=["learning"])


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: AuthTokenRequest) -> TokenResponse:
    token = learning_service.register_or_login(payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.post("/materials", response_model=MaterialResponse)
async def create_material(
    payload: MaterialCreate,
    user_id: str = Depends(get_current_user_id),
) -> MaterialResponse:
    material = await learning_service.create_material(user_id, payload.model_dump())
    return MaterialResponse.model_validate(material)


@router.post("/sessions", response_model=SessionSummaryResponse)
async def create_session(
    payload: SessionCreate,
    user_id: str = Depends(get_current_user_id),
) -> SessionSummaryResponse:
    session = await learning_service.create_session(
        user_id,
        str(payload.material_id),
        payload.learning_goal,
    )
    return SessionSummaryResponse(session_id=session["id"], status=session["status"])


@router.get("/sessions/{id}", response_model=SessionDetailResponse)
async def get_session(
    id: UUID,
    user_id: str = Depends(get_current_user_id),
) -> SessionDetailResponse:
    details = await learning_service.get_session_details(user_id, str(id))
    return SessionDetailResponse.model_validate(details)


@router.post("/sessions/{id}/next", response_model=LessonResponse)
async def next_lesson(
    id: UUID,
    payload: SessionNextRequest | None = Body(default=None),
    user_id: str = Depends(get_current_user_id),
) -> LessonResponse:
    lesson = await learning_service.generate_next_lesson(
        user_id,
        str(id),
        payload.topic if payload else None,
    )
    return LessonResponse(lesson=lesson["lesson"])


@router.post("/sessions/{id}/answer", response_model=EvaluationResponse)
async def submit_answer(
    id: UUID,
    payload: AnswerRequest,
    user_id: str = Depends(get_current_user_id),
) -> EvaluationResponse:
    result = await learning_service.process_answer(
        user_id,
        str(id),
        str(payload.question_id),
        payload.answer,
    )
    return EvaluationResponse.model_validate(result)


@router.post("/sessions/{id}/quiz", response_model=QuizResponse)
async def generate_quiz(
    id: UUID,
    payload: QuizRequest,
    user_id: str = Depends(get_current_user_id),
) -> QuizResponse:
    quiz = await learning_service.generate_quiz_for_session(
        user_id,
        str(id),
        payload.topic,
        payload.difficulty,
        payload.count,
    )
    return QuizResponse.model_validate(quiz)


@router.get("/progress", response_model=list[ProgressResponse])
async def get_progress(
    material_id: UUID | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> list[ProgressResponse]:
    rows = await learning_service.get_user_progress(
        user_id,
        str(material_id) if material_id else None,
    )
    return [ProgressResponse.model_validate(row) for row in rows]
