# INBOXPILOT 2.0 — MASTER IMPLEMENTATION PLAN

**Target Architecture:** FastAPI + PostgreSQL/Neon (with resilient local DB engine) + Groq/OpenAI AI Orchestration + Modern Responsive Frontend  
**Guiding Principle:** Build the smallest complete product loop first, ensure rock-solid user isolation and security, and systematically upgrade each module to production standards.

---

## Phase Breakdown & Execution Sequence

```
Phase 1: Project Audit & Baseline [COMPLETED]
    ↓
Phase 2: Database Schema & Migration 003 (Relational Entities & Multi-Tenant Isolation)
    ↓
Phase 3: Resilient Database Client & Core Service Layer
    ↓
Phase 4: Authentication & User Profile Management (Register, Login, Me, Export, Deletion)
    ↓
Phase 5: Advanced AI Engine Expansion (Groq Primary, Summarize, Priority, Reply, Extract)
    ↓
Phase 6: Smart Inbox & Email Provider Service (OAuth, Sync, Categorization, Phishing Radar)
    ↓
Phase 7: Productivity Loop (Email-to-Task, Deadline Radar, Decisions, Waiting-For, Daily Briefing)
    ↓
Phase 8: Tasks, Projects & Kanban Management (List, Board, Calendar)
    ↓
Phase 9: Calendar & Meeting Intelligence (Events CRUD, Agenda/Day/Week, Sync)
    ↓
Phase 10: AI Personal Assistant (Conversational RAG, Safe Tool Calls, Citations)
    ↓
Phase 11: Knowledge Hub & Follow-ups Management (Unanswered Tracking, Suggested Drafts)
    ↓
Phase 12: Visual Automation Studio (Trigger -> Condition -> Action, Execution History)
    ↓
Phase 13: Real-Time Analytics Engine (Database Metrics, Productivity Velocity)
    ↓
Phase 14: Premium UI/UX Transformation & SaaS Landing Page
    ↓
Phase 15: Security Hardening & Prompt Injection Defense
    ↓
Phase 16: Comprehensive Testing, QA & Final Audit
```

---

## Detailed Implementation Steps

### Step 1: Database Migration `003_inboxpilot_v2.sql`
- Add relational tables:
  - `connected_accounts` (user_id, provider, email_address, encrypted_tokens, sync_cursor, status)
  - `email_threads` (user_id, account_id, provider_thread_id, subject, snippet, category, priority, priority_reason, is_unread, is_starred, is_archived, latest_at)
  - `email_messages` (user_id, thread_id, provider_message_id, sender_name, sender_email, recipients, subject, body_text, body_html, received_at, is_phishing, phishing_indicators)
  - `ai_insights` (user_id, source_message_id, insight_type, structured_result, model_version)
  - `tasks` (user_id, project_id, title, description, due_at, status, priority, source_message_id, confidence)
  - `projects` (user_id, name, color, description)
  - `calendar_events` (user_id, provider_event_id, title, description, location, starts_at, ends_at, priority, source_message_id)
  - `notes` (user_id, title, body, tags, source_message_id)
  - `follow_ups` (user_id, thread_id, recipient, subject, last_sent_at, expected_by, status, suggested_action)
  - `knowledge_items` (user_id, title, content, category, tags, source_type, source_id)
  - `workflow_definitions` (user_id, name, trigger_type, conditions, actions, is_active)
  - `workflow_runs` (user_id, workflow_id, trigger_event, status, result_log, started_at)
  - `audit_events` (user_id, action, resource_type, resource_id, metadata, created_at)
- Create comprehensive indexes, foreign keys with `ON DELETE CASCADE`, and update triggers.

### Step 2: Database Client & Dual-Mode Support
- Enhance `app/db/client.py` to seamlessly connect to PostgreSQL/Neon when available, with automatic support for SQLite local fallback (`inboxpilot.db`) if remote PostgreSQL is unreachable or during offline development.
- Ensure all queries use parameterized execution and user-level isolation.

### Step 3: Security & Encryption Helpers
- Implement Fernet/AES token encryption helper (`app/core/crypto.py`) to safely encrypt OAuth tokens at rest.
- Update `app/core/security.py` with explicit registration, login, token refresh, and user profile helpers.

### Step 4: AI Engine Intelligence Expansion
- Add specialized schemas in `app/ai_engine/models.py`:
  - `EmailSummaryResult`: overview, key_points, decisions, questions, next_steps.
  - `PriorityResult`: score (HIGH/MEDIUM/LOW), urgency, importance, reasoning.
  - `ReplyDraftResult`: replies in 5 tones (professional, friendly, formal, concise, persuasive).
  - `TaskExtractionResult`: list of tasks (title, description, due_date, priority, confidence).
  - `SecurityAnalysisResult`: is_suspicious, risk_score, indicators, safety_tips.
  - `AssistantChatResult`: answer, sources, suggested_actions.
- Add prompt engineering in `app/ai_engine/prompts.py` with strict XML/markdown untrusted content demarcation to prevent prompt injection.
- Configure Groq as primary with OpenAI/Gemini fallback.

### Step 5: Email Provider & Synchronization Service
- Implement `app/services/email_service.py`:
  - Gmail API integration (OAuth2 token exchange, message fetch, thread sync, draft creation).
  - Sample provider seeding for immediate offline demonstration when credentials are pending.
  - Email categorization and priority scoring automation.
  - Category correction endpoint storing user preferences.

### Step 6: Productivity Automation Services
- Implement `app/services/task_service.py` (CRUD, status transitions, Kanban grouping, project assignment).
- Implement `app/services/calendar_service.py` (Events CRUD, Agenda, Day, Week views).
- Implement `app/services/productivity_service.py`:
  - Email-to-Task approval flow.
  - Deadline Radar aggregator.
  - Decision Tracker.
  - Waiting-For tracker.
  - Daily AI Briefing generator.

### Step 7: Assistant, Knowledge Hub, Follow-ups, and Automation
- Implement `app/services/assistant_service.py`: context-aware RAG querying user's recent messages, tasks, and calendar events.
- Implement `app/services/knowledge_service.py` & `app/services/followup_service.py`.
- Implement `app/services/automation_service.py` (Trigger -> Condition -> Action evaluation engine).
- Implement `app/services/analytics_service.py` (Real metric calculations).

### Step 8: FastAPI Router Integration
- Expose modular API routers under `/api/v1/`:
  - `/auth`: register, login, me, profile, change-password, export, delete.
  - `/emails`: accounts, sync, threads, messages, categorize, summarize, draft-reply, extract-tasks, security-check.
  - `/tasks`: CRUD, status, projects, email-to-task approval.
  - `/calendar`: CRUD, agenda, deadlines.
  - `/productivity`: briefing, radar, decisions, waiting-for.
  - `/assistant`: query, conversation history.
  - `/knowledge`: search, create, update, delete.
  - `/follow-ups`: list, snooze, resolve, generate-draft.
  - `/automations`: workflows CRUD, test, trigger, history.
  - `/analytics`: overview, velocity, category breakdown.

### Step 9: Frontend 2.0 Overhaul
- **Landing Page:** Interactive marketing page with hero, live preview, feature tour, security details, pricing tiers, and auth modals.
- **App Command Center:** Daily briefing card, priority email preview, deadline radar, focus mode toggle.
- **Smart Inbox UI:** Category tabs, search & filters, thread viewer, summary modal, reply generator with tone selector, suspicious email warning banner.
- **Task Management UI:** Toggle between List View, Kanban Board, and Calendar View.
- **Calendar UI:** Interactive month, week, day, and agenda views with event creation.
- **AI Assistant Chat:** Floating/dedicated conversational interface with citation cards.
- **Knowledge Hub & Follow-ups UI:** Card grid, search, snooze, and draft triggers.
- **Automation Studio UI:** Visual node-based or card-based workflow editor.
- **Analytics Dashboard UI:** Clean SVG/CSS data visualization charts.

### Step 10: Rigorous QA & Verification
- Unit and integration tests covering all new routes, DB migrations, AI tools, and security boundaries.
- Verify 100% test pass rate with zero regression.
- Produce final documentation (`FINAL_AUDIT.md`, `DEPLOYMENT_GUIDE.md`, `CHANGELOG.md`).
