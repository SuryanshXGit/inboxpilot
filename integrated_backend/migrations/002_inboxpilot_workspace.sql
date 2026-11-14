-- 002_inboxpilot_workspace.sql
-- Adds the InboxPilot workspace document table.
-- Safe to run more than once; no existing table is modified destructively.

BEGIN;

-- The trigger helper is created by 001; recreate it harmlessly so this
-- migration also works when run on its own.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- inboxpilot_workspaces
-- One validated JSON document per user (tasks, events, messages, notes,
-- approval_state). A single document keeps the browser sync contract simple.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS inboxpilot_workspaces (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    state           JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_inboxpilot_workspaces_updated_at ON inboxpilot_workspaces;
CREATE TRIGGER trg_inboxpilot_workspaces_updated_at
    BEFORE UPDATE ON inboxpilot_workspaces
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
