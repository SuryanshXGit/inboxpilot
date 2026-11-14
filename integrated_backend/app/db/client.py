"""Neon Serverless PostgreSQL connection helpers (psycopg v3)."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from urllib.parse import urlparse

import psycopg
from psycopg import Cursor
from psycopg.rows import dict_row

from app.core.config import settings


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


@contextmanager
def get_db() -> Iterator[Cursor]:
    """Yield a dictionary-row cursor and commit when the block succeeds.

    The connection context manager rolls the transaction back automatically if
    an exception escapes the ``with`` block, so callers never have to handle
    transaction cleanup themselves.
    """

    with psycopg.connect(
        settings.DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=10,
        **_connection_kwargs(),
    ) as conn:
        with conn.cursor() as cur:
            yield cur
            conn.commit()
