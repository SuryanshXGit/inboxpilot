"""Shared pytest configuration.

Settings are instantiated at import time, so tests must provide safe fallbacks
before importing the application. The unit tests never open a real database or
call a real AI provider.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes-long")

# Force provider credentials off so the suite can never spend API credits,
# even if the developer's shell exports real keys.
os.environ["OPENAI_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["AI_PRIMARY_PROVIDER"] = "openai"
os.environ["AI_FALLBACK_PROVIDER"] = "groq"
