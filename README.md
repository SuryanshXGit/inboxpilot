# InboxPilot

InboxPilot is a small personal workspace: tasks, calendar events, an inbox,
notes and an approval flag. The static frontend works on its own and syncs to a
FastAPI backend backed by PostgreSQL when you sign in.

- **Backend** — FastAPI + psycopg 3, JWT auth, one validated workspace document
  per user, plus the existing learning/quiz API.
- **Frontend** — plain HTML/CSS/JavaScript, no build step. Keeps a local copy as
  an offline cache and reconciles it with the backend.

## Layout

```text
.
├── integrated_backend/      FastAPI service, migrations and tests
│   ├── app/                 application code
│   ├── migrations/          SQL migrations (001, 002)
│   ├── tests/               pytest suite
│   └── README.md            backend details and API reference
└── frontend/                static InboxPilot UI (index.html, app.js, styles.css)
```

## Quick start

Requirements: Python 3.11+, PostgreSQL (or a hosted provider such as Neon) and
`psql` for the migrations.

```bash
cd integrated_backend
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install dependencies and configure the environment:

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: Copy-Item .env.example .env
```

Edit `.env` and set at least:

- `DATABASE_URL` — PostgreSQL connection string
- `JWT_SECRET` — a long random string
  (`python -c "import secrets; print(secrets.token_urlsafe(64))"`)
- `OPENAI_API_KEY` and/or `GROQ_API_KEY` if you use the AI lesson features

The checked-in `.env.example` points the UI at this repository:

```env
INBOXPILOT_DIR=../frontend
```

Apply the migrations and start the server:

```bash
psql "$DATABASE_URL" -f migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f migrations/002_inboxpilot_workspace.sql
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/inboxpilot/>. In the UI, open **Profile and
settings → Profile & login → Connect to backend** and enter an email and
password. New accounts are registered automatically on first sign-in.

- Swagger UI: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

## Tests

```bash
cd integrated_backend
python -m pytest -q
```

The suite uses in-memory database doubles and mocked AI providers, so it needs
no live database and consumes no API credits.

## Workspace API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/workspace` | Current user's workspace (empty on first use) |
| `PUT` | `/api/v1/workspace` | Replace the current user's workspace |
| `POST` | `/api/v1/auth/token` | Register or log in, returns a JWT |

The workspace document stores `tasks`, `events`, `messages`, `notes` and
`approval_state`. The API validates real calendar dates, trims required text,
rejects blank entries, enforces per-list limits and marks responses
`Cache-Control: no-store`. Every row is scoped to the authenticated user.

The frontend treats the backend as authoritative while signed in, keeps
localStorage as an offline cache, tracks unsynced edits and never uploads one
account's cached workspace into another account.

## Security

- `.env` is git-ignored; only `.env.example` with placeholders is committed.
- Never commit database URLs, JWT secrets, provider keys or storage
  credentials.
- `JWT_SECRET` must be unique per deployment; generate a fresh value rather than
  reusing the example.
