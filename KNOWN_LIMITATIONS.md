# INBOXPILOT 2.0 — KNOWN LIMITATIONS & ROADMAP

The following technical items are documented as planned capabilities or external dependency constraints:

1. **Direct Google OAuth Credentials:**
   - Production synchronization with real Gmail inboxes requires registering a Google Cloud Project with the Gmail API and setting `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.
   - When credentials are not yet configured, the system provides an Interactive Demo inbox with full relational data and AI processing capabilities so users can immediately test all 10 modules.

2. **Render Free Instance Spin-up:**
   - On Render's free tier, instances spin down after inactivity. The first API call after a period of dormancy may take 30–50 seconds while the container initializes.

3. **Background Worker Deployment:**
   - Background email synchronization runs within async tasks inside FastAPI. In high-scale enterprise deployments (10,000+ users), this will be extracted into a dedicated Celery or temporal worker queue.
