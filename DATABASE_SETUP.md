# INBOXPILOT 2.0 — DATABASE SETUP GUIDE

InboxPilot 2.0 features dual-database architecture:
1. **Production:** PostgreSQL (Neon Serverless PostgreSQL or Supabase Postgres).
2. **Local Zero-Config:** Resilient embedded SQLite fallback when running offline or without remote database credentials.

---

## 1. Neon Serverless PostgreSQL Setup

### Step 1: Create a Neon Project
1. Log in to [Neon Console](https://console.neon.tech).
2. Create a new PostgreSQL database (Postgres 16 or 17).
3. Copy the pooled connection string with SSL enabled:
   ```text
   postgresql://user:password@ep-xyz-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### Step 2: Apply SQL Migrations in Sequence
Execute the 3 migrations using `psql` or the Neon SQL Editor:

```bash
psql "$DATABASE_URL" -f integrated_backend/migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f integrated_backend/migrations/002_inboxpilot_workspace.sql
psql "$DATABASE_URL" -f integrated_backend/migrations/003_inboxpilot_v2.sql
```

### Table Structure Created:
- `users`: Multi-tenant user accounts with password hashes & preferences.
- `connected_accounts`: Third-party email providers (Google, Outlook, IMAP, Demo) with encrypted OAuth tokens.
- `email_threads`: Grouped communication conversations with categories & priority ratings.
- `email_messages`: Individual email messages with headers, bodies, phishing flags, and attachments.
- `projects`: Project containers for grouping tasks.
- `tasks`: Action items with due dates, priorities, confidence ratings, and source email links.
- `calendar_events`: Calendar appointments, meeting intelligence, and location data.
- `notes`: Saved notes and collected information.
- `follow_ups`: Unanswered message tracker ("Waiting For") with reminder dates.
- `knowledge_items`: Searchable facts, decisions, and contact context.
- `workflow_definitions`: Visual automation rules (`TRIGGER -> CONDITION -> ACTION`).
- `workflow_runs`: Execution logs and audit history for automated rules.
- `ai_insights`: Structured AI decisions, thread summaries, and security evaluations.
- `audit_events`: Security audit trail for compliance and data sovereignty.

---

## 2. Local SQLite Engine (Zero-Config Development)

If `DATABASE_URL` is configured to `sqlite:///inboxpilot_local.db` or if remote Neon connection fails, InboxPilot automatically initializes the local schema into `integrated_backend/inboxpilot_local.db`.

No installation or configuration of PostgreSQL is required on the local development machine.
