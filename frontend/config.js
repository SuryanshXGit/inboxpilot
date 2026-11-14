/*
 * Deployment configuration.
 *
 * Leave this empty when the UI is served by the FastAPI app itself (same
 * origin, e.g. http://127.0.0.1:8000/inboxpilot/).
 *
 * When the UI is hosted separately (Vercel, Netlify, etc.), set the public
 * origin of the API here, with no trailing slash:
 *
 *   window.INBOXPILOT_API_BASE = 'https://inboxpilot-api.onrender.com';
 *
 * You can still override it per visit with ?api=https://other-host
 */
window.INBOXPILOT_API_BASE = '';
