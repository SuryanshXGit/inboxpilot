# INBOXPILOT 2.0 — DEPLOYMENT GUIDE

## 1. Architecture Overview

- **Frontend:** Static HTML5/CSS3/ES6 JavaScript. Deployed on Vercel, Netlify, or served directly from FastAPI at `/inboxpilot/`.
- **Backend API:** FastAPI (Python 3.13) with Uvicorn. Deployed on Render, Fly.io, or Railway.
- **Database:** Neon Serverless PostgreSQL or Supabase Postgres.
- **AI Inference:** Groq API (Primary, `openai/gpt-oss-120b`) with OpenAI (`gpt-4o-mini`) fallback.

---

## 2. Environment Variables Checklist

Set these variables in your Render / Railway hosting dashboard:

| Variable | Description | Example Value |
|---|---|---|
| `DATABASE_URL` | Neon PostgreSQL pooled connection string | `postgresql://user:pass@ep-xyz-pooler.neon.tech/neondb?sslmode=require` |
| `JWT_SECRET` | 64-character random string | Generated via `secrets.token_urlsafe(64)` |
| `AI_PRIMARY_PROVIDER` | Primary AI provider | `groq` |
| `AI_FALLBACK_PROVIDER` | Fallback AI provider | `openai` |
| `GROQ_API_KEY` | Groq API Key | `gsk_...` |
| `GROQ_MODEL` | Groq Model ID | `openai/gpt-oss-120b` |
| `GROQ_REASONING_EFFORT` | Reasoning intensity | `low` |
| `OPENAI_API_KEY` | OpenAI API Key | `sk-proj-...` |
| `INBOXPILOT_DIR` | Path to static frontend | `../frontend` |
| `CORS_ORIGINS` | Allowed frontend domains | `https://inboxpilot-frontend-five.vercel.app,http://localhost:8000` |

---

## 3. Render Deployment (`render.yaml`)

```yaml
services:
  - type: web
    name: inboxpilot-api
    env: python
    region: ohio
    plan: free
    rootDir: integrated_backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.13.1
      - key: AI_PRIMARY_PROVIDER
        value: groq
      - key: AI_FALLBACK_PROVIDER
        value: openai
```

---

## 4. Vercel Static Frontend Deployment

1. Set Project Root to `frontend/`.
2. Configure `frontend/config.js`:
   ```javascript
   window.INBOXPILOT_API_BASE = 'https://inboxpilot-api-v8mp.onrender.com';
   ```
3. Deploy!
