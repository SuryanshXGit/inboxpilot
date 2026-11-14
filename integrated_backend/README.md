# Integrated Learning Backend

One FastAPI application combining Person 1's learning API/database work with
Person 2's AI engine (lesson generation, quiz generation and answer evaluation).

The application keeps the existing public API, authentication, PostgreSQL
persistence and ownership checks. AI work runs in-process as importable Python
functions behind `app/ai_engine/`; there is no second HTTP server.

---

## 1. Project layout

```text
integrated_backend/
├── app/
│   ├── main.py                     # single FastAPI entrypoint, CORS, error handlers
│   ├── api/
│   │   └── v1/
│   │       ├── learning.py         # public /api/v1 learning routes
│   │       └── workspace.py        # InboxPilot workspace sync routes
│   ├── core/
│   │   ├── config.py               # env settings (core + AI providers)
│   │   └── security.py             # JWT auth, PBKDF2 password hashing
│   ├── db/
│   │   └── client.py               # psycopg v3 PostgreSQL connection helper
│   ├── schemas/
│   │   ├── learning.py             # Pydantic request/response models
│   │   └── workspace.py            # InboxPilot workspace document models
│   ├── services/
│   │   ├── learning_service.py     # SQL, ownership checks, AI boundary adapter
│   │   └── workspace_service.py    # InboxPilot workspace persistence
│   └── ai_engine/
│       ├── __init__.py             # public generate_lesson / generate_quiz / evaluate_answer
│       ├── models.py               # typed results + typed errors
│       ├── providers.py            # OpenAI, Groq, Gemini + retries/fallback
│       ├── prompts.py              # lesson, quiz, evaluation and repair prompts
│       └── graph.py                # LangGraph prepare → generate → validate → repair
├── migrations/
│   ├── 001_initial_schema.sql      # preserved from Person 1
│   └── 002_inboxpilot_workspace.sql # InboxPilot workspace document table
├── tests/
│   ├── conftest.py
│   ├── test_api.py                 # Person 1's original API suite (unchanged)
│   ├── test_workspace_api.py       # InboxPilot workspace auth + round-trip
│   ├── test_ai_engine.py           # AI providers, fallback, validation, repair
│   └── test_integration_ai.py      # typed AI results through the real endpoints
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 2. What was integrated

### From the core backend (Person 1)

| Module | Responsibility | Status |
|---|---|---|
| `app/main.py` | FastAPI app, CORS, health, startup logging, DB error handler | Preserved + extended |
| `app/api/v1/learning.py` | Auth, materials, sessions, lessons, quizzes, answers, progress | Preserved |
| `app/core/security.py` | JWT issue/verify, PBKDF2 password hashing | Preserved |
| `app/db/client.py` | PostgreSQL connection and transaction helper | Preserved |
| `app/schemas/learning.py` | Request validation and response models | Preserved |
| `app/services/learning_service.py` | Ownership-scoped SQL + AI calls | Preserved + adapter for typed AI results |
| `migrations/001_initial_schema.sql` | users, materials, sessions, messages, quiz_questions, quiz_attempts, progress | Preserved, unchanged |
| `tests/test_api.py` | Person 1's original API suite (unchanged; 16 functions / 18 cases) | Preserved, unchanged |

### From the AI engine (Person 2)

| Module | Responsibility |
|---|---|
| `app/ai_engine/models.py` | `LessonResult`, `QuizResult`, `QuizQuestion`, `EvaluationResult`, typed errors |
| `app/ai_engine/providers.py` | OpenAI primary + Groq fallback, optional Gemini, timeouts, bounded retries, rate-limit handling |
| `app/ai_engine/prompts.py` | Grounded teaching, quiz, evaluation and one-shot repair prompts |
| `app/ai_engine/graph.py` | LangGraph workflow: prepare → generate → validate → repair (once) |
| `app/ai_engine/__init__.py` | `generate_lesson()`, `generate_quiz()`, `evaluate_answer()` |

The AI engine has **no FastAPI imports, no HTTP server, no database access and no
database writes**. The service layer owns persistence.

> **Important integration note:** Person 1's source project was read from
> `C:\Users\Suryansh\Downloads\backend` and left untouched; `backend_1/`
> (Person 2's folder) was not present anywhere on the machine used for this
> integration. Person 1's project shipped only a temporary mock
> `app/ai_engine/__init__.py`. The engine above was
> implemented against the official handoff contract in
> `Person_2_AI_Engine_Agents_Guide.pdf` (exact function names, argument names,
> Pydantic fields and error names) and Person 1's mock signatures. No Person 2
> source files were overwritten because none existed. If a Person 2 folder is
> supplied later, its provider implementations can be dropped into
> `providers.py`/`graph.py` without changing the API or database layers.

---

## 3. Quick start

### Prerequisites

- Python **3.11+** (verified on Python 3.13)
- PostgreSQL connection string (Supabase Postgres, Neon, or standard PostgreSQL)
- At least one AI provider API key (OpenAI and/or Groq recommended)

### 3.1 Create and activate a virtual environment

Windows PowerShell:

```powershell
cd integrated_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
cd integrated_backend
python3 -m venv .venv
source .venv/bin/activate
```

### 3.2 Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 Configure environment variables

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Edit `.env` and replace the placeholders. Required values:

- `DATABASE_URL` — PostgreSQL/Supabase connection string
- `JWT_SECRET` — long random string (generate with
  `python -c "import secrets; print(secrets.token_urlsafe(64))"`)
- `OPENAI_API_KEY` and/or `GROQ_API_KEY` — unless you configure another provider

Never commit `.env`. It is already ignored by `.gitignore`. Do not put the
Supabase service-role key in this application; database access uses
`DATABASE_URL` only.

### 3.4 Apply the database migration

```bash
psql "$DATABASE_URL" -f migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f migrations/002_inboxpilot_workspace.sql
```

On Windows PowerShell:

```powershell
psql $env:DATABASE_URL -f migrations/001_initial_schema.sql
psql $env:DATABASE_URL -f migrations/002_inboxpilot_workspace.sql
```

The migration is idempotent (`CREATE TABLE IF NOT EXISTS`) and creates no
duplicate tables. It contains no destructive statements. If the tables already
exist, it is safe to run again.

### 3.5 Start FastAPI

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

or:

```bash
python -m app.main
```

### 3.6 Open Swagger

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Health check: <http://127.0.0.1:8000/health>

### 3.7 Run the tests

```bash
python -m pytest -q
```

Tests mock all AI providers and use an in-memory database double. They never
consume API credits and never require a live database.

---

## 4. Configuration reference

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | yes | — | PostgreSQL/Supabase connection string |
| `JWT_SECRET` | yes | — | HS256 signing secret |
| `JWT_ALGORITHM` | no | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `1440` | Token lifetime |
| `CORS_ORIGINS` | no | `*` | Comma-separated allow-list |
| `INBOXPILOT_DIR` | no | — | Path to the InboxPilot static frontend; served at `/inboxpilot/` when the folder exists |
| `LOG_LEVEL` | no | `INFO` | Log verbosity |
| `AI_PRIMARY_PROVIDER` | no | `openai` | `openai`, `groq`, `gemini` |
| `AI_FALLBACK_PROVIDER` | no | `groq` | Tried once if primary fails; `none` disables |
| `AI_TIMEOUT_SECONDS` | no | `30` | Per-request HTTP timeout |
| `AI_MAX_RETRIES` | no | `1` | Bounded retries (0–5) for transient errors |
| `AI_RETRY_BACKOFF_SECONDS` | no | `0.5` | Initial exponential backoff |
| `AI_MAX_OUTPUT_TOKENS` | no | `2500` | Provider output cap |
| `AI_TEMPERATURE` | no | `0.2` | Generation temperature |
| `AI_MAX_MATERIAL_CHARS` | no | `12000` | Material excerpt cap sent to the model |
| `AI_MAX_CONVERSATION_MESSAGES` | no | `10` | Recent history cap |
| `OPENAI_API_KEY` | conditional | — | OpenAI credentials |
| `OPENAI_MODEL` | no | `gpt-4o-mini` | OpenAI model |
| `OPENAI_BASE_URL` | no | — | Optional OpenAI-compatible gateway |
| `GROQ_API_KEY` / `GROQ_MODEL` | conditional | — / `openai/gpt-oss-120b` | Groq credentials (fallback by default) |
| `GROQ_REASONING_EFFORT` | no | `low` | gpt-oss reasoning depth; `low` keeps latency in seconds, `none` disables |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | optional | — / `gemini-2.5-flash` | Gemini support |

All existing Person 1 environment variable names are preserved. S3 and Neon AI
Gateway placeholders remain in `.env.example` for the separate ingestion work
package, although this application does not call them.

---

## 5. API endpoints

All public routes are under `/api/v1` and require a Bearer token except
`POST /api/v1/auth/token`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/v1/auth/token` | Auto-register or login; returns JWT |
| `POST` | `/api/v1/materials` | Create a learning material |
| `POST` | `/api/v1/sessions` | Create a learning session for owned material |
| `GET` | `/api/v1/sessions/{id}` | Session details + message history |
| `POST` | `/api/v1/sessions/{id}/next` | Generate and persist the next AI lesson |
| `POST` | `/api/v1/sessions/{id}/quiz` | Generate and persist AI quiz questions |
| `POST` | `/api/v1/sessions/{id}/answer` | Evaluate an answer and update progress |
| `GET` | `/api/v1/progress` | Current user's progress (optional `material_id` filter) |
| `GET` | `/api/v1/workspace` | InboxPilot workspace document (empty on first use) |
| `PUT` | `/api/v1/workspace` | Replace the authenticated user's InboxPilot workspace |

Every session/answer query is scoped by the authenticated `user_id`; another
user's session or material returns `404`.

### InboxPilot bridge

`INBOXPILOT_DIR` points at the InboxPilot frontend folder. When it exists the
app mounts it at `/inboxpilot/` (and redirects `/` there), so the UI and API
share one origin. The UI signs in through the existing `/api/v1/auth/token`
endpoint and syncs tasks, events, inbox messages, notes and the approval flag
through `GET/PUT /api/v1/workspace`. Each user gets one validated JSON document;
the API checks real calendar dates, trims required text and rejects blank
entries, and marks responses `Cache-Control: no-store`.

The browser keeps a local copy as an offline cache and records unsynced
("dirty") edits. After a reload it pushes those edits before pulling, so a
failed save is not overwritten by an older backend copy; switching accounts
never uploads another account's cached workspace. The learning tables and
routes are untouched.

---

## 6. AI engine contract

```python
async def generate_lesson(
    *, material_text: str, topic: str | None, student_level: str,
    learning_goal: str | None, conversation_history: list[dict] | None,
) -> LessonResult

async def generate_quiz(
    *, material_text: str, topic: str, difficulty: str, count: int,
) -> QuizResult

async def evaluate_answer(
    *, question: str, expected_answer: str, student_answer: str, rubric: str,
) -> EvaluationResult
```

### Result models

- `LessonResult`: `title`, `explanation`, `key_points`, `examples`,
  `check_for_understanding`, `suggested_next_topic`
- `QuizResult`: `topic`, `questions[]`
- `QuizQuestion`: `question`, exactly four `options`, `correct_option_index`
  (0–3), `explanation`, `difficulty`
- `EvaluationResult`: `is_correct`, `score` (0–1), `feedback`, `misconception`
  (nullable), `next_step`

### Persistence adaptation

The original service expected a string lesson, a list of quiz dicts and a dict
evaluation. The typed engine output is normalised in
`learning_service.py`:

- Lessons are stored as JSON text in `messages.content`.
- Quiz questions are stored in `quiz_questions.question_json`.
- `correct_option_index` is mapped to `expected_answer` and `explanation` to
  `rubric`, so the existing answer endpoint works without a schema change.
- Evaluations are stored in `quiz_attempts` and update `progress`.

Older/mocked engines returning plain strings/lists still work. This is covered
by Person 1's unchanged tests.

### Reliability

- HTTP timeouts on every provider call.
- One bounded retry for transient failures (timeouts, transport errors, HTTP
  408/409/425/429/5xx). Permanent errors (400/401/403) are never retried.
- If the primary fails, the configured fallback is tried once.
- Malformed/invalid JSON gets exactly one repair attempt, then a typed
  `AIOutputInvalid` error.
- If all providers fail, `AIProviderUnavailable` is raised.
- The service converts engine failures to HTTP `502` with a safe message.
- Database failures return HTTP `503` with `{"detail": "Database unavailable"}`.
- Logs contain provider names and status codes only — never API keys, prompts,
  student answers or response bodies.

---

## 7. Conflicts found and how they were resolved

| # | Conflict | Resolution |
|---|---|---|
| 1 | `backend_1/` (Person 2) was absent; only a mock AI module existed | Implemented the engine against the documented handoff contract; preserved mock-compatible calls; documented the gap. No original files deleted. |
| 2 | Documented engine returns Pydantic models; service expected `str`/`list`/`dict` | Added `model_payload()` and `_coerce_quiz_questions()` adapters in the service. Both typed and legacy outputs work. |
| 3 | Documented quiz schema uses `correct_option_index`; existing evaluation expects `expected_answer`/`rubric` | Normalisation maps the correct option into `expected_answer` and explanation into `rubric`; no migration needed. |
| 4 | Mock signature allowed positional args; handoff contract uses keyword-only args | Engine exports keyword-only functions with defaults; the service already calls by keyword. |
| 5 | Task description said Supabase; actual Person 1 code uses Neon/`psycopg` with `DATABASE_URL` | Preserved the working implementation. It works with Supabase Postgres via the same connection string; no duplicate client or tables added. |
| 6 | Two dependency sets (core + AI) | Consolidated into one `requirements.txt`; used `httpx` adapters instead of four vendor SDKs, eliminating SDK version conflicts. |
| 7 | Two environment-variable sets | Merged into one `.env.example`; no existing variable renamed and no `.env` overwritten. |
| 8 | AI output could be malformed or crash the API | Added Pydantic validation, one repair attempt, typed errors, safe 502 responses. |
| 9 | Database errors could leak connection details | Added a `psycopg.Error` handler returning a safe 503. |
| 10 | Person 2's engine must not write to the database | AI engine imports no DB/FastAPI modules; persistence stays in `learning_service.py`. |
| 11 | Existing tests expect the old AI boundary | Preserved `tests/test_api.py` unchanged; added adapter integration tests. |
| 12 | Anthropic Claude was the default fallback | Project owner asked to replace it with Groq. The Claude adapter, config fields, env vars and tests were removed; Groq (OpenAI-compatible) is now the default fallback and a regression test asserts `anthropic` is rejected. |
| 13 | Default Groq model `llama-3.3-70b-versatile` no longer exists | A live `/models` call showed Groq's current catalogue; the default is now `openai/gpt-oss-120b`. |
| 14 | `gpt-oss` took ~68 s per lesson/quiz/evaluation | Groq defaults to heavy reasoning. `GROQ_REASONING_EFFORT=low` is now sent, cutting engine latency to ~1.6 s and full requests to ~8 s. |
| 15 | Every request took ~68 s against the live database | Windows prefers IPv6 and this network has no IPv6 route, so libpq spent ~45 s on AAAA records before falling back. `app/db/client.py` now pins an IPv4 `hostaddr` (cached); connect time dropped from 47 s to ~2.5 s. The previous `503` on a missing session also returned to `404`. |
| 16 | OpenAI key returned HTTP 429 during live testing | Documented, not "fixed": the key is out of quota/rate-limited. `.env` was switched to `AI_PRIMARY_PROVIDER=groq`, keeping OpenAI as fallback. |

---

## 8. Verification results

Environment: Windows, Python 3.13, clean virtual environment, dependencies
installed from `requirements.txt`.

| Check | Result |
|---|---|
| `python -m compileall app tests` | Passed |
| Import check (`app.main`, AI engine modules) | Passed with required env vars |
| `pip check` | `No broken requirements found` |
| Test suite | **62 passed** in ~16 s |
| Real Uvicorn startup | Passed; `/health` 200, `/docs` 200, `/openapi.json` 200 |
| FastAPI startup lifespan | Passed; logs provider availability names only |
| Existing Person 1 API tests | 18 passed, unchanged |
| AI success/retry/fallback tests | Passed (mocked providers) |
| Invalid AI output + repair tests | Passed |
| Provider adapter parsing tests | Passed (OpenAI, Groq, Gemini shapes) |
| Unauthorized access tests | Passed |
| Database failure safe-503 test | Passed |
| DB connection helper tests | Passed (IPv4 pinning, DNS failure, explicit `hostaddr`) |
| **Live PostgreSQL (Neon)** | **Verified** — migrations 001 and 002 applied, 8 tables, CRUD round-trip |
| **Live Groq lesson/quiz/evaluation** | **Verified** — real calls returned valid typed output (~8 s per endpoint) |
| Live OpenAI calls | **Blocked by the account** — HTTP 429 (quota/rate limit), documented |
| Live Gemini calls | **Not verified** — no key configured |
| Browser UI (`/docs`) | **Verified** — Swagger UI loads and lists all 11 operations |
| **InboxPilot UI + sync** | **Verified** — served at `/inboxpilot/`, sign-in, save/reload, and cross-user isolation through live Neon |

The live run created a temporary account, material and session, then deleted
them (`DELETE FROM users ...` cascaded), leaving all tables at 0 rows.

---

## 9. Remaining manual setup

1. Create `.env` from `.env.example` and fill in real credentials. *(Done locally.)*
2. Run the migration against the real PostgreSQL/Supabase database. *(Done locally.)*
3. Start the server and exercise the Swagger UI. *(Done locally.)*
4. Optionally smoke-test one real lesson/quiz/evaluation with a provider key. *(Done with Groq.)*
5. If Person 2's original `backend_1/` becomes available, compare its provider
   and prompt modules with this implementation and port any extra behavior;
   the public function signatures and result models above are the stable
   contract.
6. For production, restrict `CORS_ORIGINS`, rotate secrets, enable database
   backups/RLS as appropriate, and run behind TLS.

---

## 10. Security notes

- API keys are read only from the server environment; they are never returned
  by the API or written to logs.
- `.env` is ignored by git; `.env.example` contains placeholders only.
- JWTs are required on all learning routes; ownership is enforced in SQL.
- Passwords use PBKDF2-HMAC-SHA256 with per-user random salts.
- AI prompts tell the model to treat student answers/material as data, reducing
  prompt-injection risk; outputs are still validated before persistence.
- Database errors are logged by exception type only, not by SQL or DSN.
- No destructive migration or data deletion is performed.
