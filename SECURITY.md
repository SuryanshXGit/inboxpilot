# INBOXPILOT 2.0 — SECURITY & PRIVACY POLICY

Security and human control are foundational release blockers for InboxPilot 2.0.

---

## 1. Untrusted Data Isolation & Prompt Injection Defense

All external email content, headers, subject lines, and attachments are treated as **untrusted data**.
- Prompt templates strictly enclose email text inside `<untrusted_email>` XML delimiter blocks.
- System instructions explicitly forbid AI models from interpreting instructions or imperative commands contained inside email bodies.
- Emails cannot declare their own priority, authorize actions, or bypass security rules.

---

## 2. Token & Secret Encryption at Rest

- All third-party OAuth access tokens and refresh tokens are encrypted at rest using counter-mode authenticated encryption with HMAC-SHA256 (`app/core/crypto.py`).
- Encryption keys are derived via SHA-256 from the server's private `JWT_SECRET`.
- Plaintext provider tokens are never logged and never exposed to the frontend browser.

---

## 3. Human Approval Policy

Consequential operations always require explicit human approval:
- **Email Sending:** AI drafts contextual replies; emails are **never** sent automatically without user review and confirmation.
- **Task Creation from Email:** Extracted tasks present confidence scores and previews. The user confirms or edits before persistence.
- **Calendar Scheduling:** External calendar invites require review.
- **Account Deletion:** Immediate cascading delete across all tables upon user request.

---

## 4. Multi-Tenant Authorization

Every database query without exception enforces tenant isolation:
```sql
WHERE user_id = %s
```
Frontend client requests cannot access, view, or modify other users' emails, tasks, calendar events, or workflows.
