# Deployment integration contract

This deployment owns orchestration only; it does not edit backend or frontend code.

## Backend image contract

- `backend/Dockerfile` must produce an image containing `manage.py`, `config.wsgi:application`, and Gunicorn, and listen on **0.0.0.0:8000**.
- The image entrypoint must be safe to override. Compose overrides it with `entrypoint: []`; API containers run Gunicorn directly.
- The one-shot `init` service is the **only** migration/collectstatic owner. Do not run migrations in the API entrypoint, otherwise replicas can race.
- `python manage.py migrate --noinput` and `collectstatic --noinput` must succeed with the supplied MySQL environment and `/app/staticfiles` volume.
- `/api/health/` must be an unauthenticated, fast HTTP 2xx endpoint. API healthchecks call it locally.
- API containers need writable `/app/media` only for uploads; Nginx intentionally returns 404 for public `/media/` to avoid leaking private data. Add authenticated API download endpoints if media is required.
- Redis is available at `REDIS_URL=redis://redis:6379/0`; no public port is published.

## Frontend contract

- The frontend image must listen on `0.0.0.0:3000`; Nginx proxies `/` to the `frontend` service.
- Browser API calls must remain same-origin `/api/...`; Nginx owns API routing and rate limits.
- Current CSP permits `'unsafe-inline'` for Next.js inline bootstrap. This is a known residual risk; migrate to nonce/hash-based CSP after confirming the generated scripts and then remove it.

## Operational notes

Copy `.env.example` to `.env`, replace every placeholder, and run `docker compose config` before starting. No DB, Redis, API, or frontend port is published directly; only Nginx's configured HTTP port is published. `compose.production.yaml` is a TLS deployment template, not proof that HTTPS is live.
