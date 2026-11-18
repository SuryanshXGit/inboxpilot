# INBOXPILOT 2.0 — MISSING FEATURES & GAPS INVENTORY

Derived from the **InboxPilot 2.0 Product Blueprint** and project specifications, the following components are required to graduate InboxPilot from a hackathon prototype into a full-scale AI productivity platform.

---

## 1. Product Identity & Design System
- [ ] **Public SaaS Landing Page:** Modern marketing landing page featuring product hero, value propositions, interactive UI showcase, security architecture, transparent pricing (free beta / planned tiers), and sign-up/login modal.
- [ ] **10-Module Navigation Hierarchy:** Full implementation of:
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
- [ ] **Unified Design System:** Premium typography, consistent spacing scales, rich responsive card states (loading skeletons, empty states, error fallbacks, badge tags).

---

## 2. Authentication & User Profile Management
- [ ] Explicit `POST /api/v1/auth/register` and `POST /api/v1/auth/login` endpoints with distinct validation.
- [ ] `GET /api/v1/auth/me` and `PUT /api/v1/auth/profile` for user profile and preferences.
- [ ] Password reset / change flows.
- [ ] Account deletion (`DELETE /api/v1/auth/me`) cascading through all user data for GDPR/privacy compliance.
- [ ] User data export (`GET /api/v1/auth/export`) delivering complete user records in JSON format.
- [ ] Google OAuth connection flow for Gmail & Google Calendar synchronization.

---

## 3. Smart Inbox & Email Provider Integration
- [ ] **Email Provider Connection Service:** Support connecting email accounts (Google OAuth Gmail API and IMAP/SMTP standard fallback).
- [ ] **Relational Storage:** Relational models for `connected_accounts`, `email_threads`, and `email_messages`.
- [ ] **Sync Engine:** Incremental synchronization with cursor/history ID tracking, preventing duplicate syncs, handling token refresh, and tracking sync timestamps.
- [ ] **Inbox Categories:** Automatic categorization into Primary, Work, Personal, Education, Finance, Promotions, Updates, Important, and Spam/Suspicious.
- [ ] **Category Override:** Ability for users to manually reclassify messages, with preference learning.
- [ ] **Search & Filtering:** Search by sender, subject, body, date range; filters for Unread, Starred, Category, and Priority.

---

## 4. Advanced AI Email Intelligence
- [ ] **Thread & Email Summarization:** Extract concise summary, key points, decisions made, questions asked, and next steps.
- [ ] **Explainable Priority Scoring:** Score messages (High, Medium, Low) based on deadlines, direct requests, VIP senders, and urgency language, with an explicit explanation string ("Why this priority?").
- [ ] **AI Reply Generator:** Generate context-aware drafts in 5 distinct tones:
  - Professional
  - Friendly
  - Formal
  - Concise & Direct
  - Persuasive
- [ ] **Attachment Intelligence:** Safe extraction of text, dates, deliverables, and financial amounts from uploaded documents (PDF, TXT) with strict size limits and validation.
- [ ] **Suspicious Email Detection:** Flag phishing cues, domain spoofing, suspicious links, and urgent payment requests with risk score and actionable safety guidelines.

---

## 5. Email-to-Productivity Automation
- [ ] **Email-to-Task Pipeline:** One-click extraction of actionable tasks from emails (title, description, due date, priority, source message ID, confidence score) with human confirmation preview.
- [ ] **Deadline Radar:** Aggregated view of all impending deadlines across emails, tasks, and calendar events.
- [ ] **Meeting Intelligence:** Extraction of suggested meeting times, attendees, agendas, and action items.
- [ ] **Decision Tracker:** Log of decisions reached in conversations linked to original email threads.
- [ ] **Waiting For:** Tracking sent requests awaiting replies from colleagues or vendors.
- [ ] **Daily AI Briefing:** Morning briefing combining unread priority items, today's schedule, urgent follow-ups, and overdue tasks.
- [ ] **Focus Mode:** Distraction-free view filtering only top 3-5 critical items.

---

## 6. Tasks & Projects Management
- [ ] Full task lifecycle (Todo, In Progress, Blocked, Completed).
- [ ] Multi-view presentation: List View, Kanban Board, and Calendar View.
- [ ] Project grouping and tag filters.
- [ ] Due date filtering: Today, Tomorrow, This Week, Overdue.

---

## 7. Calendar & Meeting Intelligence
- [ ] Agenda, Day, Week, and Month views.
- [ ] Create, edit, and delete events with timezone awareness.
- [ ] Direct linking between calendar events and source email conversations.
- [ ] Google Calendar two-way synchronization option.

---

## 8. AI Personal Assistant
- [ ] Context-aware conversational assistant chat interface.
- [ ] Tool calling / retrieval over authorized user data (emails, tasks, calendar, notes).
- [ ] Structured answers with direct citations and links to original source items.
- [ ] Strict prompt-injection safeguards (treating user email bodies as untrusted data).

---

## 9. Knowledge Hub
- [ ] Searchable personal knowledge base storing decisions, notes, contact insights, and project briefs.
- [ ] Source provenance tracking linking every item to its originating thread or note.
- [ ] Full-text search and topic tagging.

---

## 10. Follow-up Management
- [ ] Unanswered email detector tracking sent messages expecting a reply.
- [ ] Suggested follow-up date calculation based on message urgency.
- [ ] One-click follow-up draft generator.
- [ ] Snooze and mark-resolved controls.

---

## 11. Visual Automation Studio
- [ ] Visual workflow builder implementing `TRIGGER -> CONDITION -> ACTION`.
- [ ] Triggers: New Email, Important Email Detected, Deadline Approaching, Task Overdue, Follow-up Due.
- [ ] Actions: Create Task, Create Draft, Add Note, Set Category, Send In-App Reminder.
- [ ] Workflow execution history, error handling, manual trigger, enable/disable switches, and approval gates for sensitive actions.

---

## 12. Productivity Analytics Dashboard
- [ ] Real-time database metrics: Emails Processed, Important vs Low Priority, Task Completion Velocity, Overdue Backlog, Follow-up Response Times.
- [ ] Visual productivity trend charts.
