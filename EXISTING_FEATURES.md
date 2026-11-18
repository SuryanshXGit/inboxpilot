# INBOXPILOT 2.0 — EXISTING FEATURES INVENTORY

This document identifies all functional, partially implemented, and simulated capabilities found in the existing codebase prior to the 2.0 transformation.

---

## 1. Authentication & Session Management

| Feature | Implementation State | Technical Details |
|---|---|---|
| Password Hashing | **Completed & Solid** | PBKDF2-HMAC-SHA256, 260,000 iterations, 16-byte random salt, constant-time verification. |
| Access Token Generation | **Completed & Solid** | PyJWT, HS256, expiration tracking via `ACCESS_TOKEN_EXPIRE_MINUTES`. |
| Token Verification Dependency | **Completed & Solid** | `get_current_user_id` FastAPI security dependency enforcing Bearer scheme and returning UUID. |
| Auto-Registration / Login | **Partially Completed** | `/api/v1/auth/token` automatically creates an account if email does not exist, or validates password if it does. Needs split into explicit register & login. |
| Refresh Tokens | **Missing** | Access token is long-lived without rotation. |
| User Profile & Preferences | **Partially Completed** | User table has `display_name`, but preferences are stored only in frontend `localStorage`. |
| Account Deletion & Export | **Missing** | No endpoint exists to delete user account and cascade delete all stored data. |

---

## 2. Workspace Document Store

| Feature | Implementation State | Technical Details |
|---|---|---|
| Single-Document API | **Completed** | `GET /api/v1/workspace` and `PUT /api/v1/workspace` provide atomic document replacement. |
| User Scoping | **Completed** | Strict `WHERE user_id = %s` in PostgreSQL query. Verified in tests. |
| Schema Validation | **Completed** | Pydantic `WorkspaceState` validates tasks, events, messages, notes, and approval status. |
| Offline Cache & Conflict Resolution | **Completed** | Frontend keeps local copy in `localStorage`, tracks `dirty` state and revision, prompts user before overwriting remote edits. |

---

## 3. Artificial Intelligence Engine

| Feature | Implementation State | Technical Details |
|---|---|---|
| Provider Adapter Architecture | **Completed & Solid** | `BaseProvider` with unified `generate()` contract. Direct `httpx` integration without SDK lock-in. |
| Groq Support | **Completed & Verified** | Configured with `openai/gpt-oss-120b`, supports `reasoning_effort: low` to maintain fast response times. Tested live HTTP 200. |
| OpenAI Support | **Completed & Verified** | Configured with `gpt-4o-mini`, JSON mode. Tested live HTTP 200. |
| Gemini Support | **Completed** | Adapter written for Google Generative Language API. |
| Bounded Retries & Fallback | **Completed & Solid** | Retries transient HTTP errors (429, 5xx, timeouts) up to bounded budget; falls back to secondary provider. |
| LangGraph Orchestration | **Partially Completed** | Small graph (`prepare -> generate -> validate -> repair`) implemented for legacy learning tasks. Needs extension to email intelligence. |
| Email Intelligence Tasks | **Missing** | Thread summarization, priority scoring, reply drafting, and task extraction are not yet wired to the AI engine. |

---

## 4. User Interface & Frontend

| Feature | Implementation State | Technical Details |
|---|---|---|
| Responsive Navigation | **Completed** | Sidebar navigation with desktop collapse and mobile hamburger drawer. |
| Theme System | **Completed** | Light, Dark, and Midnight background themes supported via CSS variables. |
| Modal & Dialog System | **Completed** | Keyboard-accessible dialogs with focus trapping and ESC dismissal. |
| Overview Dashboard | **Partially Completed** | Renders summary metric cards, goal input box, and calendar previews. Relies on demo numbers. |
| Mock Inbox View | **Simulated / Demo** | Displays 3 hardcoded messages. No backend email sync. |
| Task List | **Completed** | Add, toggle done, delete tasks; stored in workspace document. |
| Interactive Calendar | **Completed** | Monthly grid, date navigation, day event listing, priority indicators (high/medium/low). |
| Notes & Collected Info | **Completed** | Note creation and rendering within workspace. |
| Approval Flow | **Simulated / Demo** | Static draft for "Venue availability". Has Approve/Reject buttons updating `approvalState`. |
| Local File Library | **Partially Completed** | Browser-local file upload into IndexedDB/storage. No server-side attachment extraction. |
| Plugins Directory | **Simulated / Demo** | Static cards showcasing planned integrations. |

---

## 5. Deployment & Configuration

| Feature | Implementation State | Technical Details |
|---|---|---|
| Monorepo Serving | **Completed** | FastAPI mounts the frontend static directory at `/inboxpilot/` if configured, enabling single-port local dev. |
| CORS Configuration | **Completed** | Dynamic CORS allow-list with wildcard rejection when credentials are required. |
| Safe DB Error Handling | **Completed** | `psycopg.Error` handler returns HTTP 503 without leaking connection strings or SQL queries. |
| Render & Vercel Config | **Completed** | `render.yaml` for backend deployment; `vercel.json` and `config.js` for frontend static deployment. |
