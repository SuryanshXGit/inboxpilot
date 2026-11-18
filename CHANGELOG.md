# INBOXPILOT 2.0 — CHANGELOG

## [2.0.0] - November 2026

### Added
- **Core SaaS Navigation:** Implemented complete 10-module architecture:
  1. Command Center
  2. Smart Inbox
  3. AI Assistant
  4. Tasks & Projects
  5. Calendar
  6. Knowledge Hub
  7. Follow-ups
  8. Automation Studio
  9. Analytics
  10. Settings & Privacy
- **Public SaaS Landing Page:** Added high-converting landing page with hero, live interface preview, feature breakdowns, security specifications, transparent pricing, and direct auth modal triggers.
- **Relational Database Schema:** Added `migrations/003_inboxpilot_v2.sql` with tables for connected accounts, email threads, messages, tasks, projects, calendar events, notes, follow-ups, knowledge items, workflows, workflow runs, and audit logs.
- **Resilient Dual-Mode Database Engine:** Added zero-config local SQLite fallback supporting immediate offline execution without 503 errors when remote PostgreSQL is unreachable.
- **Advanced AI Email Intelligence:**
  - AI Thread Summarization (key points, decisions, questions, next steps)
  - Explainable Priority Intelligence (HIGH/MEDIUM/LOW with human-readable rationale)
  - AI Reply Drafter supporting 5 distinct tones (Professional, Friendly, Formal, Concise, Persuasive)
  - Email-to-Task extraction with confidence ratings and preview confirmation
  - Suspicious email and phishing heuristic detector with risk indicators
  - Context-aware AI Personal Assistant answering questions across authorized user records
- **Productivity Loop:** Added Daily AI Briefing, Deadline Radar, Waiting-For tracker, and Deep Work Focus Mode.
- **Visual Automation Studio:** Added `TRIGGER -> CONDITION -> ACTION` workflow builder with execution test simulation and run history logging.
- **Real-Time Analytics:** Added live database productivity analytics with category distribution and weekly velocity trends.
- **Security Hardening:** Added token encryption at rest via `app/core/crypto.py`, prompt-injection defense with untrusted data isolation, and GDPR export/deletion endpoints.
- **Test Suite:** Added 14 comprehensive tests in `tests/test_inboxpilot_v2.py`. Total test count increased from 66 to 80 (100% passing).

### Changed
- Configured Groq as the primary high-speed AI provider with OpenAI as fallback.
- Upgraded frontend design system with Plus Jakarta Sans typography, dark/light theme switcher, fluid modal transitions, and responsive mobile sidebar.
- Preserved 100% of existing workspace document sync and legacy learning routes for full backwards compatibility.
