"""FastAPI application entrypoint for the integrated backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.ai_engine.providers import configured_providers
from app.api.v1.analytics import router as analytics_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.auth import router as auth_router
from app.api.v1.automation import router as automation_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.email import router as email_router
from app.api.v1.followups import router as followups_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.learning import router as learning_router
from app.api.v1.productivity import router as productivity_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.workspace import router as workspace_router
from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Log configuration names only. Never log keys, prompts or student data.
    providers = configured_providers()
    if providers:
        logger.info(
            "AI providers available: %s (primary=%s, fallback=%s)",
            ", ".join(providers),
            settings.primary_provider or "none",
            settings.fallback_provider or "none",
        )
    else:
        logger.warning(
            "No AI provider credentials configured; AI endpoints will return 502 until "
            "OPENAI_API_KEY / GROQ_API_KEY (or another provider) is set."
        )
    yield


app = FastAPI(
    title="InboxPilot 2.0 API",
    version="2.0.0",
    description=(
        "InboxPilot 2.0 AI-Powered Communication & Productivity Command Center API. "
        "Smart Inbox, AI Email Intelligence, Tasks & Projects, Calendar, Personal Assistant, "
        "Knowledge Hub, Follow-up Tracking, Visual Automation Studio, and Analytics."
    ),
    lifespan=lifespan,
)

cors_origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(psycopg.Error)
async def database_error_handler(request: Request, exc: psycopg.Error) -> JSONResponse:
    """Return a safe 503 instead of leaking connection details or SQL."""

    logger.error(
        "Database error handling %s %s (%s)",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database unavailable"},
    )


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "OK"}


# Core 2.0 Routers
app.include_router(auth_router)
app.include_router(email_router)
app.include_router(tasks_router)
app.include_router(productivity_router)
app.include_router(calendar_router)
app.include_router(assistant_router)
app.include_router(knowledge_router)
app.include_router(followups_router)
app.include_router(automation_router)
app.include_router(analytics_router)

# Legacy Routers for backwards compatibility
app.include_router(workspace_router)
app.include_router(learning_router)

# Serve the InboxPilot static frontend from the same origin when configured.
# Keeping it under /inboxpilot leaves the API and Swagger routes untouched.
_frontend_dir = settings.inboxpilot_dir
if _frontend_dir is not None:
    logger.info("Serving InboxPilot frontend from %s", _frontend_dir)
    app.mount(
        "/inboxpilot",
        StaticFiles(directory=str(_frontend_dir), html=True),
        name="inboxpilot",
    )

    @app.get("/", include_in_schema=False)
    def frontend_root() -> RedirectResponse:
        return RedirectResponse(url="/inboxpilot/")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
