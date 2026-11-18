# InboxPilot 2.0 — Complete AI Communication & Productivity Command Center

InboxPilot 2.0 is a premium AI-powered productivity platform that understands communication, extracts deadlines, prioritizes high-stakes conversations, and turns information into verified, trackable action—keeping users in full control.

---

## 🌟 Key Highlights & Modules

1. **Executive Command Center:** Daily AI Briefing, urgent conversation triage, deadline radar, focus mode, and today's schedule.
2. **Smart Inbox:** Provider synchronization (Gmail / Outlook / Demo), 9 automated categories (Primary, Work, Personal, Education, Finance, Promotions, Updates, Important, Spam/Suspicious), explainable priority scoring, and unread/starred filtering.
3. **Advanced AI Email Intelligence:** Sub-second thread summarization, explainable priority scoring, contextual reply drafting in 5 tones (Professional, Friendly, Formal, Concise, Persuasive), and phishing/spoofing detection with risk indicators.
4. **Email-to-Task Pipeline:** Extracts actionable tasks and deadlines from communications with confidence scoring and human approval before database persistence.
5. **Tasks & Projects:** Multi-view task manager (List View and 4-Column Kanban Board) with status tracking (Todo, In Progress, Blocked, Completed) and project grouping.
6. **Meeting & Calendar Intelligence:** Interactive monthly grid, daily agendas, and meeting extraction.
7. **AI Personal Assistant:** Natural-language conversational interface querying authorized user emails, tasks, and calendar events with source citations.
8. **Knowledge Hub:** Searchable personal knowledge base storing approved facts, decisions, and contact context.
9. **Follow-ups ("Waiting For"):** Detects unanswered outgoing emails and tracks expected response dates.
10. **Visual Automation Studio:** Visual workflow builder (`TRIGGER -> CONDITION -> ACTION`) with simulation test execution and run history audit logs.
11. **Productivity Analytics:** Live database metrics on emails processed, completion velocity, time saved, and weekly trends.
12. **Settings, Privacy & Security:** Profile customization, encrypted OAuth tokens at rest, GDPR export (.json), and permanent account deletion.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.11+
- Git
- Optional: PostgreSQL / Neon Serverless (the app automatically falls back to a high-performance local SQLite database if PostgreSQL credentials are not provided).

### 2. Activate Virtual Environment & Install Dependencies

```powershell
# Windows PowerShell
cd integrated_backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# macOS / Linux
cd integrated_backend
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env        # Windows: Copy-Item .env.example .env
```

Edit `.env` and configure your settings:
- `GROQ_API_KEY` — (Primary high-speed AI provider)
- `OPENAI_API_KEY` — (Fallback AI provider)
- `JWT_SECRET` — (Secret key for signing tokens and deriving symmetric encryption keys)
- `DATABASE_URL` — (PostgreSQL connection string; or leave as SQLite for zero-config local development)

### 4. Run Migrations & Start Server

For PostgreSQL / Neon:
```bash
psql "$DATABASE_URL" -f migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f migrations/002_inboxpilot_workspace.sql
psql "$DATABASE_URL" -f migrations/003_inboxpilot_v2.sql
```

Start the application:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at:
- **Web Application & Landing Page:** <http://127.0.0.1:8000/> (or <http://127.0.0.1:8000/inboxpilot/>)
- **Interactive Swagger Docs:** <http://127.0.0.1:8000/docs>
- **Health Check:** <http://127.0.0.1:8000/health>

---

## 🧪 Test Suite

Run the complete 80-test suite:

```bash
cd integrated_backend
python -m pytest -v
```

**Result:** 80/80 tests passing (100% pass rate).

---

## 🔒 Security Architecture

1. **Untrusted Data Boundary:** All incoming email bodies and attachments are marked as untrusted data using data delimiters (`<untrusted_email>`). Models are instructed to never execute instructions embedded in emails.
2. **Encrypted Tokens:** OAuth provider tokens are symmetrically encrypted at rest using counter-mode authenticated encryption (`app/core/crypto.py`).
3. **Multi-Tenant Isolation:** Object-level authorization enforced on every database query (`WHERE user_id = %s`).
4. **Human In The Loop:** Consequential operations (sending emails, saving extracted tasks, calendar invites) require explicit user approval.
