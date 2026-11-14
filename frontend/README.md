# InboxPilot frontend

InboxPilot is a static HTML/CSS/JS workspace. It can run on its own (data stays
in the browser) or sync to the **integrated_backend** FastAPI service.

## Option A — served by the backend (recommended)

The backend serves this folder at `/inboxpilot/` when `INBOXPILOT_DIR` points
to it. From `integrated_backend/`:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open <http://127.0.0.1:8000/inboxpilot/>.

Open **Profile → Profile & login → Connect to backend**, enter an email and
password (the backend auto-registers new accounts), and the workspace starts
syncing. The status pill in the bottom-left shows the current state.

## Option B — separate static server

Stop the backend from serving this folder if you prefer, then run a static
server on a different port (the backend already uses 8000):

```bash
py -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500/>. The page calls
`http://127.0.0.1:8000` by default. Override it with a query parameter:

```text
http://127.0.0.1:5500/?api=http://127.0.0.1:8000
```

The backend allows the cross-origin request (`CORS_ORIGINS=*` by default) and
accepts the JWT in the `Authorization` header.

## What syncs

Tasks, calendar events, inbox messages, notes and the approval flag are saved
through `GET/PUT /api/v1/workspace`. The browser keeps a local copy so the UI
still works offline; failed writes stay local and are retried on the next
change. Library files remain in IndexedDB by design.
