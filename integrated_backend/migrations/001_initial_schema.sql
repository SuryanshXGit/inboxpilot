-- 001_initial_schema.sql
-- Initial schema for Person 1's learning work package (Neon PostgreSQL).
-- Safe to run more than once; objects are created only when missing.

BEGIN;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

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
-- users
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enforce case-insensitive uniqueness even if a row is inserted outside the API.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower
    ON users (LOWER(email));

-- ---------------------------------------------------------------------------
-- learning_materials
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS learning_materials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    extracted_text  TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_materials_user_id
    ON learning_materials (user_id);
CREATE INDEX IF NOT EXISTS idx_learning_materials_user_created
    ON learning_materials (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- learning_sessions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS learning_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    material_id     UUID NOT NULL REFERENCES learning_materials(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'paused', 'completed')),
    current_topic   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_user_id
    ON learning_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_material_id
    ON learning_sessions (material_id);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_user_status
    ON learning_sessions (user_id, status);

DROP TRIGGER IF EXISTS trg_learning_sessions_updated_at ON learning_sessions;
CREATE TRIGGER trg_learning_sessions_updated_at
    BEFORE UPDATE ON learning_sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- messages
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session_created
    ON messages (session_id, created_at ASC);

-- ---------------------------------------------------------------------------
-- quiz_questions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quiz_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    question_json   JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_questions_session_created
    ON quiz_questions (session_id, created_at ASC);

-- ---------------------------------------------------------------------------
-- quiz_attempts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answer          TEXT NOT NULL,
    score           NUMERIC(5, 4) NOT NULL DEFAULT 0
                    CHECK (score >= 0 AND score <= 1),
    feedback        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_created
    ON quiz_attempts (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_question_id
    ON quiz_attempts (question_id);

-- ---------------------------------------------------------------------------
-- progress
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS progress (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    material_id     UUID NOT NULL REFERENCES learning_materials(id) ON DELETE CASCADE,
    topic           TEXT NOT NULL,
    mastery_score   NUMERIC(5, 4) NOT NULL DEFAULT 0
                    CHECK (mastery_score >= 0 AND mastery_score <= 1),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT progress_user_material_topic_key
        UNIQUE (user_id, material_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_progress_user_id
    ON progress (user_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_material
    ON progress (user_id, material_id);

DROP TRIGGER IF EXISTS trg_progress_updated_at ON progress;
CREATE TRIGGER trg_progress_updated_at
    BEFORE UPDATE ON progress
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
