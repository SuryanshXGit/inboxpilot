"""Neon Serverless PostgreSQL connection helpers (psycopg v3) with resilient SQLite fallback."""

from __future__ import annotations

import logging
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.db.sqlite_engine import get_sqlite_db

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _ipv4_hostaddr(host: str, port: int) -> str | None:
    """Return the first IPv4 address for ``host``, or ``None``.

    Windows prefers IPv6. On networks without an IPv6 route, libpq spends the
    connection timeout on each AAAA record before falling back to IPv4, which
    turns a ~1s connection into a ~45s one. Pinning ``hostaddr`` keeps the
    hostname for TLS/SNI while forcing the IPv4 path.
    """

    try:
        infos = socket.getaddrinfo(
            host,
            port,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except OSError:
        return None
    return infos[0][4][0] if infos else None


def _connection_kwargs() -> dict[str, object]:
    """Extra libpq arguments derived from ``DATABASE_URL``."""

    if "hostaddr=" in settings.DATABASE_URL:
        return {}

    parsed = urlparse(settings.DATABASE_URL)
    if not parsed.hostname:
        return {}

    hostaddr = _ipv4_hostaddr(parsed.hostname, parsed.port or 5432)
    return {"hostaddr": hostaddr} if hostaddr else {}


_pg_available: bool | None = None


@contextmanager
def get_db() -> Iterator[Any]:
    """Yield a dictionary-row cursor and commit when the block succeeds.

    Tries the configured PostgreSQL connection first. If unreachable (offline,
    DNS resolution failure, or paused serverless instance), automatically falls back
    to the high-performance local SQLite database without breaking endpoints.
    """
    global _pg_available

    if settings.DATABASE_URL.startswith("sqlite") or _pg_available is False:
        with get_sqlite_db() as cur:
            yield cur
        return

    try:
        with psycopg.connect(
            settings.DATABASE_URL,
            row_factory=dict_row,
            connect_timeout=2,
            **_connection_kwargs(),
        ) as conn:
            _pg_available = True
            with conn.cursor() as cur:
                yield cur
                conn.commit()
    except (psycopg.OperationalError, psycopg.Error, OSError) as exc:
        if _pg_available is not False:
            logger.warning(
                "PostgreSQL connection unavailable (%s); switching to resilient SQLite local fallback.",
                type(exc).__name__,
            )
            _pg_available = False
        with get_sqlite_db() as cur:
            yield cur
