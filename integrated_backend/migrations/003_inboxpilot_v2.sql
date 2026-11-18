-- 003_inboxpilot_v2.sql
-- Complete relational schema for InboxPilot 2.0 AI Productivity Platform.
-- Supports PostgreSQL / Neon. Safe to execute repeatedly.

BEGIN;

-- Helper trigger for automatic updated_at timestamp updates
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- Add preferences column to users if not present
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- ---------------------------------------------------------------------------
-- 1. Connected Email & Calendar Accounts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS connected_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider            TEXT NOT NULL CHECK (provider IN ('google', 'outlook', 'imap', 'demo')),
    email_address       TEXT NOT NULL,
    encrypted_tokens    TEXT NOT NULL DEFAULT '',
    scopes              TEXT NOT NULL DEFAULT '',
    sync_cursor         TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disconnected', 'error', 'syncing')),
    last_synced_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_connected_accounts_user_id ON connected_accounts(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_connected_accounts_user_provider_email 
    ON connected_accounts(user_id, provider, LOWER(email_address));

DROP TRIGGER IF EXISTS trg_connected_accounts_updated_at ON connected_accounts;
CREATE TRIGGER trg_connected_accounts_updated_at
    BEFORE UPDATE ON connected_accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 2. Email Threads
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_threads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id          UUID REFERENCES connected_accounts(id) ON DELETE CASCADE,
    provider_thread_id  TEXT NOT NULL DEFAULT '',
    subject             TEXT NOT NULL DEFAULT '',
    snippet             TEXT NOT NULL DEFAULT '',
    category            TEXT NOT NULL DEFAULT 'Primary' 
                        CHECK (category IN ('Primary', 'Work', 'Personal', 'Education', 'Finance', 'Promotions', 'Updates', 'Important', 'Spam/Suspicious')),
    priority            TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW')),
    priority_reason     TEXT NOT NULL DEFAULT '',
    is_unread           BOOLEAN NOT NULL DEFAULT true,
    is_starred          BOOLEAN NOT NULL DEFAULT false,
    is_archived         BOOLEAN NOT NULL DEFAULT false,
    latest_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_threads_user_latest ON email_threads(user_id, latest_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_threads_user_category ON email_threads(user_id, category);
CREATE INDEX IF NOT EXISTS idx_email_threads_user_priority ON email_threads(user_id, priority);
CREATE INDEX IF NOT EXISTS idx_email_threads_provider_thread ON email_threads(user_id, provider_thread_id);

DROP TRIGGER IF EXISTS trg_email_threads_updated_at ON email_threads;
CREATE TRIGGER trg_email_threads_updated_at
    BEFORE UPDATE ON email_threads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 3. Email Messages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thread_id           UUID NOT NULL REFERENCES email_threads(id) ON DELETE CASCADE,
    provider_message_id TEXT NOT NULL DEFAULT '',
    sender_name         TEXT NOT NULL DEFAULT '',
    sender_email        TEXT NOT NULL DEFAULT '',
    recipients          JSONB NOT NULL DEFAULT '[]'::jsonb,
    subject             TEXT NOT NULL DEFAULT '',
    body_text           TEXT NOT NULL DEFAULT '',
    body_html           TEXT NOT NULL DEFAULT '',
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_phishing         BOOLEAN NOT NULL DEFAULT false,
    phishing_indicators JSONB NOT NULL DEFAULT '[]'::jsonb,
    attachments         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_messages_thread_id ON email_messages(thread_id, received_at ASC);
CREATE INDEX IF NOT EXISTS idx_email_messages_user_received ON email_messages(user_id, received_at DESC);

-- ---------------------------------------------------------------------------
-- 4. Projects
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    color               TEXT NOT NULL DEFAULT '#6366f1',
    description         TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);

-- ---------------------------------------------------------------------------
-- 5. Tasks
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id          UUID REFERENCES projects(id) ON DELETE SET NULL,
    source_message_id   UUID REFERENCES email_messages(id) ON DELETE SET NULL,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    due_at              TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'completed', 'blocked', 'canceled')),
    priority            TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low', 'urgent')),
    confidence          FLOAT NOT NULL DEFAULT 1.0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON tasks(user_id, due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);

DROP TRIGGER IF EXISTS trg_tasks_updated_at ON tasks;
CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 6. Calendar Events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calendar_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_message_id   UUID REFERENCES email_messages(id) ON DELETE SET NULL,
    provider_event_id   TEXT NOT NULL DEFAULT '',
    title               TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    location            TEXT NOT NULL DEFAULT '',
    starts_at           TIMESTAMPTZ NOT NULL,
    ends_at             TIMESTAMPTZ NOT NULL,
    all_day             BOOLEAN NOT NULL DEFAULT false,
    priority            TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_user_starts ON calendar_events(user_id, starts_at ASC);

DROP TRIGGER IF EXISTS trg_calendar_events_updated_at ON calendar_events;
CREATE TRIGGER trg_calendar_events_updated_at
    BEFORE UPDATE ON calendar_events
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 7. Notes & Collected Information
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_message_id   UUID REFERENCES email_messages(id) ON DELETE SET NULL,
    title               TEXT NOT NULL,
    body                TEXT NOT NULL DEFAULT '',
    tags                JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_user_created ON notes(user_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_notes_updated_at ON notes;
CREATE TRIGGER trg_notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 8. Follow-ups & Waiting For
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS follow_ups (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thread_id           UUID REFERENCES email_threads(id) ON DELETE CASCADE,
    recipient           TEXT NOT NULL,
    subject             TEXT NOT NULL,
    last_sent_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expected_by         TIMESTAMPTZ NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'replied', 'snoozed', 'dismissed')),
    suggested_action    TEXT NOT NULL DEFAULT '',
    draft_reply         TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_follow_ups_user_status ON follow_ups(user_id, status);
CREATE INDEX IF NOT EXISTS idx_follow_ups_user_expected ON follow_ups(user_id, expected_by ASC);

DROP TRIGGER IF EXISTS trg_follow_ups_updated_at ON follow_ups;
CREATE TRIGGER trg_follow_ups_updated_at
    BEFORE UPDATE ON follow_ups
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 9. Knowledge Hub Items
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    content             TEXT NOT NULL,
    category            TEXT NOT NULL DEFAULT 'general',
    tags                JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_type         TEXT NOT NULL DEFAULT 'manual' CHECK (source_type IN ('email', 'attachment', 'note', 'task', 'manual')),
    source_id           TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_items_user_category ON knowledge_items(user_id, category);

-- ---------------------------------------------------------------------------
-- 10. Visual Automation Studio (Definitions & Runs)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    trigger_type        TEXT NOT NULL CHECK (trigger_type IN ('email_received', 'priority_high', 'deadline_approaching', 'task_overdue', 'follow_up_due')),
    conditions          JSONB NOT NULL DEFAULT '[]'::jsonb,
    actions             JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active           BOOLEAN NOT NULL DEFAULT true,
    requires_approval   BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflows_user_active ON workflow_definitions(user_id, is_active);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workflow_id         UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    trigger_event       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failed', 'pending_approval')),
    result_summary      TEXT NOT NULL DEFAULT '',
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_user_started ON workflow_runs(user_id, started_at DESC);

-- ---------------------------------------------------------------------------
-- 11. AI Insights & Decisions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_insights (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_message_id   UUID REFERENCES email_messages(id) ON DELETE CASCADE,
    insight_type        TEXT NOT NULL CHECK (insight_type IN ('summary', 'priority', 'task_extraction', 'decision', 'security', 'briefing')),
    structured_result   JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version       TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_insights_user_type ON ai_insights(user_id, insight_type);
CREATE INDEX IF NOT EXISTS idx_ai_insights_message ON ai_insights(source_message_id);

-- ---------------------------------------------------------------------------
-- 12. Security Audit Log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action              TEXT NOT NULL,
    resource_type       TEXT NOT NULL,
    resource_id         TEXT NOT NULL DEFAULT '',
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address          TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_user_created ON audit_events(user_id, created_at DESC);

COMMIT;
