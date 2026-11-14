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
from app.api.v1.learning import router as learning_router
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
    title="Interactive Learning API",
    version="1.1.0",
    description=(
        "Person 1's learning API integrated with Person 2's AI engine. "
        "Authentication, materials, sessions, quizzes, progress and AI-powered "
        "lesson generation live behind one FastAPI application."
    ),
    lifespan=lifespan,
)

cors_origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    # Browsers reject wildcard origins combined with credentials. JWTs are sent
    # in the Authorization header, so credentials are only enabled for an
    # explicit allow-list.
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


app.include_router(learning_router)
app.include_router(workspace_router)

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
