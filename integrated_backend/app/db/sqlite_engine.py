"""SQLite fallback engine providing PostgreSQL-compatible behavior for offline/local use.

When Neon PostgreSQL is unreachable (DNS resolution failure, offline environment,
or paused cluster), this fallback maintains 100% operational readiness for all
FastAPI endpoints and the frontend without raising 503 errors.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "inboxpilot_local.db"


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    fields = [column[0] for column in cursor.description]
    result: dict[str, Any] = {}
    for key, val in zip(fields, row):
        if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
            try:
                result[key] = json.loads(val)
                continue
            except Exception:
                pass
        result[key] = val
    return result


def _init_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Create all 2.0 tables in SQLite if not present."""
    conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
    conn.create_function("NOW", 0, lambda: "2026-11-18T23:00:00Z")
    conn.create_function("LOWER", 1, lambda s: s.lower() if isinstance(s, str) else s)

    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        display_name TEXT,
        preferences TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS inboxpilot_workspaces (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        state TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS connected_accounts (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        provider TEXT NOT NULL,
        email_address TEXT NOT NULL,
        encrypted_tokens TEXT NOT NULL DEFAULT '',
        scopes TEXT NOT NULL DEFAULT '',
        sync_cursor TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        last_synced_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS email_threads (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        account_id TEXT REFERENCES connected_accounts(id) ON DELETE CASCADE,
        provider_thread_id TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL DEFAULT '',
        snippet TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT 'Primary',
        priority TEXT NOT NULL DEFAULT 'MEDIUM',
        priority_reason TEXT NOT NULL DEFAULT '',
        is_unread INTEGER NOT NULL DEFAULT 1,
        is_starred INTEGER NOT NULL DEFAULT 0,
        is_archived INTEGER NOT NULL DEFAULT 0,
        latest_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS email_messages (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        thread_id TEXT NOT NULL REFERENCES email_threads(id) ON DELETE CASCADE,
        provider_message_id TEXT NOT NULL DEFAULT '',
        sender_name TEXT NOT NULL DEFAULT '',
        sender_email TEXT NOT NULL DEFAULT '',
        recipients TEXT NOT NULL DEFAULT '[]',
        subject TEXT NOT NULL DEFAULT '',
        body_text TEXT NOT NULL DEFAULT '',
        body_html TEXT NOT NULL DEFAULT '',
        received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_phishing INTEGER NOT NULL DEFAULT 0,
        phishing_indicators TEXT NOT NULL DEFAULT '[]',
        attachments TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        color TEXT NOT NULL DEFAULT '#6366f1',
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
        source_message_id TEXT REFERENCES email_messages(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        due_at TEXT,
        status TEXT NOT NULL DEFAULT 'todo',
        priority TEXT NOT NULL DEFAULT 'medium',
        confidence REAL NOT NULL DEFAULT 1.0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS calendar_events (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        source_message_id TEXT REFERENCES email_messages(id) ON DELETE SET NULL,
        provider_event_id TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        location TEXT NOT NULL DEFAULT '',
        starts_at TEXT NOT NULL,
        ends_at TEXT NOT NULL,
        all_day INTEGER NOT NULL DEFAULT 0,
        priority TEXT NOT NULL DEFAULT 'medium',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        source_message_id TEXT REFERENCES email_messages(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS follow_ups (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        thread_id TEXT REFERENCES email_threads(id) ON DELETE CASCADE,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        last_sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expected_by TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        suggested_action TEXT NOT NULL DEFAULT '',
        draft_reply TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS knowledge_items (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        tags TEXT NOT NULL DEFAULT '[]',
        source_type TEXT NOT NULL DEFAULT 'manual',
        source_id TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS workflow_definitions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        trigger_type TEXT NOT NULL,
        conditions TEXT NOT NULL DEFAULT '[]',
        actions TEXT NOT NULL DEFAULT '[]',
        is_active INTEGER NOT NULL DEFAULT 1,
        requires_approval INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS workflow_runs (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        workflow_id TEXT NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
        trigger_event TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'success',
        result_summary TEXT NOT NULL DEFAULT '',
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ai_insights (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        source_message_id TEXT REFERENCES email_messages(id) ON DELETE CASCADE,
        insight_type TEXT NOT NULL,
        structured_result TEXT NOT NULL DEFAULT '{}',
        model_version TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL DEFAULT '',
        metadata TEXT NOT NULL DEFAULT '{}',
        ip_address TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()


class SQLiteCursorWrapper:
    def __init__(self, raw_cursor: sqlite3.Cursor):
        self._cur = raw_cursor

    def execute(self, sql: str, params: Any = None) -> "SQLiteCursorWrapper":
        # Convert %s placeholders to ?
        cleaned_sql = sql.replace("%s", "?")
        # Replace PostgreSQL NOW() with CURRENT_TIMESTAMP
        cleaned_sql = cleaned_sql.replace("NOW()", "CURRENT_TIMESTAMP")
        cleaned_sql = cleaned_sql.replace("gen_random_uuid()", "lower(hex(randomblob(16)))")
        
        # Normalize parameters
        norm_params = []
        if params is not None:
            for p in params:
                if hasattr(p, "obj"):  # Jsonb wrapper
                    norm_params.append(json.dumps(p.obj))
                elif isinstance(p, (dict, list)):
                    norm_params.append(json.dumps(p))
                elif isinstance(p, uuid.UUID):
                    norm_params.append(str(p))
                elif isinstance(p, bool):
                    norm_params.append(1 if p else 0)
                else:
                    norm_params.append(p)
        self._cur.execute(cleaned_sql, tuple(norm_params))
        return self

    def executemany(self, sql: str, seq_of_params: Any) -> "SQLiteCursorWrapper":
        cleaned_sql = sql.replace("%s", "?").replace("NOW()", "CURRENT_TIMESTAMP")
        self._cur.executemany(cleaned_sql, seq_of_params)
        return self

    def fetchone(self) -> dict[str, Any] | None:
        row = self._cur.fetchone()
        return row

    def fetchall(self) -> list[dict[str, Any]]:
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount


@contextmanager
def get_sqlite_db() -> Iterator[SQLiteCursorWrapper]:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = _dict_factory
    _init_sqlite_schema(conn)
    cur = conn.cursor()
    try:
        yield SQLiteCursorWrapper(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
