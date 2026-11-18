"""Application configuration loaded from environment variables / ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Export every .env entry to os.environ as well. pydantic-settings only loads
# the fields declared below; third-party SDKs read directly from the process
# environment.
load_dotenv(BACKEND_DIR / ".env", override=False)


class Settings(BaseSettings):
    """Runtime settings for the integrated learning API.

    Values are read from the process environment first and then from
    ``integrated_backend/.env``. ``extra="ignore"`` keeps unrelated local
    variables (for example, the AWS variables used by an ingestion worker)
    from breaking startup.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Core / authentication ------------------------------------------------
    DATABASE_URL: str
    JWT_SECRET: str

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    CORS_ORIGINS: str = "*"
    LOG_LEVEL: str = "INFO"

    # Optional path to the InboxPilot static frontend. When the directory
    # exists the app serves it at /inboxpilot/ so both applications share one
    # origin. Leave empty to run the API only.
    INBOXPILOT_DIR: str = ""

    # -- AI provider selection ----------------------------------------------
    AI_PRIMARY_PROVIDER: str = "groq"
    AI_FALLBACK_PROVIDER: str = "openai"

    # Reliability. Retries are bounded and apply only to transient errors.
    AI_TIMEOUT_SECONDS: float = Field(default=30.0, ge=1.0, le=180.0)
    AI_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    AI_RETRY_BACKOFF_SECONDS: float = Field(default=0.5, ge=0.0, le=30.0)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=2_500, ge=256, le=16_384)
    AI_TEMPERATURE: float = Field(default=0.2, ge=0.0, le=2.0)

    # Prompt-size guards (do not send entire textbooks to a provider).
    AI_MAX_MATERIAL_CHARS: int = Field(default=12_000, ge=500, le=100_000)
    AI_MAX_CONVERSATION_MESSAGES: int = Field(default=10, ge=0, le=50)

    # -- OpenAI (primary by default) ----------------------------------------
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str | None = None

    # -- Groq (fallback by default; OpenAI-compatible endpoint) --------------
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    # gpt-oss reasons heavily by default (~1 min/request); "low" keeps latency
    # in the low seconds. Use "none" to omit the parameter.
    GROQ_REASONING_EFFORT: str = "low"

    # -- Optional Google Gemini ---------------------------------------------
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    @field_validator("AI_PRIMARY_PROVIDER", "AI_FALLBACK_PROVIDER")
    @classmethod
    def _normalise_provider(cls, value: str) -> str:
        value = (value or "").strip().lower()
        allowed = {"", "none", "openai", "groq", "gemini"}
        if value not in allowed:
            raise ValueError("provider must be one of: openai, groq, gemini, none")
        return value

    @field_validator("GROQ_REASONING_EFFORT")
    @classmethod
    def _normalise_reasoning_effort(cls, value: str) -> str:
        value = (value or "").strip().lower()
        if value in {"", "none", "off", "false"}:
            return ""
        if value not in {"low", "medium", "high"}:
            raise ValueError(
                "GROQ_REASONING_EFFORT must be one of: low, medium, high, none"
            )
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Return the configured CORS origins as a list."""

        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return origins or ["*"]

    @property
    def inboxpilot_dir(self) -> Path | None:
        """Resolved InboxPilot frontend directory, or ``None`` when absent."""

        value = self.INBOXPILOT_DIR.strip()
        if not value:
            return None
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            if (BACKEND_DIR / candidate).is_dir():
                candidate = BACKEND_DIR / candidate
            else:
                candidate = BACKEND_DIR.parent / candidate
        candidate = candidate.resolve()
        if candidate.is_dir():
            if (candidate / "frontend").is_dir() and not (candidate / "index.html").is_file():
                return (candidate / "frontend").resolve()
            return candidate
        return None

    @property
    def primary_provider(self) -> str | None:
        value = self.AI_PRIMARY_PROVIDER.strip().lower()
        return None if value in {"", "none"} else value

    @property
    def fallback_provider(self) -> str | None:
        value = self.AI_FALLBACK_PROVIDER.strip().lower()
        return None if value in {"", "none"} else value

    @property
    def groq_reasoning_effort(self) -> str | None:
        value = self.GROQ_REASONING_EFFORT.strip().lower()
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
