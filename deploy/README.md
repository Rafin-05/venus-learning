# Running Venus Learning

## Local evaluation

Install Docker Engine, Docker Compose plugin 2.24.4 or newer, and Python 3. From the release root:

```sh
cp .env.example .env
# Edit .env: replace secret placeholders and review hosts/origins.
sh scripts/validate-env.sh
docker compose build
docker compose up -d
# The one-shot init service applies migrations and collects Django static assets.
docker compose logs init
docker compose exec api1 python manage.py createsuperuser
BASE_URL=http://localhost:8080 sh scripts/smoke.sh
```

Open `http://localhost:8080`. The application administrator portal is `/admin`; Django's maintenance interface is `/django-admin/`. Do not use a default or shared administrator password. Do not run the old PHP application's migration URL.

Nginx is the only published service. It distributes API requests between `api1` and `api2` using least connections. MySQL and Redis are internal services; Django sessions persist across API replicas. Inspect Nginx logs to see the selected upstream address.

The `.env.example` values intentionally permit **local HTTP evaluation**. They are not a secure public deployment. Email is printed to backend logs by the local console backend; treat those logs as sensitive because they contain verification/reset links. Never publish verification links in logs accessible to users.

## Public HTTPS deployment

1. Point the domain's DNS to the host and obtain a valid certificate for that domain. Certificate issuance/renewal is an operator responsibility.
2. Place the certificate chain at `deploy/tls/fullchain.pem` and private key at `deploy/tls/privkey.pem`. Restrict private-key access and never put it into a release ZIP or version control.
3. Set `ALLOWED_HOSTS` to the real domain plus `127.0.0.1` for internal health checks. Never use `*`. Set `FRONTEND_URL=https://your-domain.example` and matching `CSRF_TRUSTED_ORIGINS=https://your-domain.example`.
4. Set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, valid SMTP host/credentials/sender, and appropriate TLS settings. Test mailbox verification and password reset with an address you own.
5. Keep `DEBUG=false` and `ENABLE_DEMO_ACCOUNTS=false`. Set `SECURE_SSL_REDIRECT=true`, `SESSION_COOKIE_SECURE=true`, `CSRF_COOKIE_SECURE=true`, and `TRUST_PROXY=true`. The production override disables demo mode for both API services and the init job, and enforces the HTTPS flags on API services. Use a fresh production database, not local demo volumes. Keep the backend reachable only through the controlled proxy.
6. Run the production configuration:

```sh
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up -d --build
BASE_URL=https://your-domain.example sh scripts/smoke.sh
```

The production override replaces published ports with 80 and 443, redirects HTTP to HTTPS, and enables HSTS. It requires a modern Compose plugin because it uses `!override`. Read the resolved configuration before first deployment without sharing its contents: environment values can include secrets.

Nginx overwrites forwarded-client-IP/protocol headers. Do not expose API containers directly or trust unverified forwarded headers from clients. If adding another CDN/proxy, configure trusted real-IP handling explicitly; otherwise request limits will identify the intermediary rather than the end user.

## Coding exercises

Configure `JUDGE0_URL` and, if required by your runner, `JUDGE0_API_KEY`. Use a dedicated isolated Judge0-compatible execution service with outbound network restrictions, CPU/memory/time limits, and authentication. Never use the application host or MySQL host as an untrusted-code execution worker. An unconfigured runner must return a clear unavailable response, not award a successful grade.

## Storage, updates, and recovery

Persistent volumes hold MySQL, Redis, Django static files, and media. Do not use `docker compose down -v` on a live deployment: it removes named volumes and destroys persisted data. Back up MySQL and any media with access controls, encryption, retention limits, and a tested restore procedure. Take a backup before schema changes.

For an update, build images, back up the database, run migrations once, then recreate both API containers and the frontend. The init service avoids two API replicas racing to apply migrations. For later releases, explicitly run:

```sh
docker compose run --rm init
docker compose up -d --build api1 api2 frontend nginx
```

Review `docker compose ps`, application logs, SMTP delivery, authentication failures, and error rates after updates. The included setup is a single-host deployment with an API load balancer, not highly available MySQL, a WAF, a managed backup service, or automatic failover across machines.

## Browser security and uploads

Nginx adds framing, MIME-sniffing, referrer and permissions headers. Next.js dynamically renders pages with a fresh per-request script nonce and a strict script CSP; inline styles remain allowed. Do not put HTML behind a cache that reuses nonce-bearing responses. API responses use a restrictive policy and no-store caching. Public `/media/` delivery is blocked; files use `/api/uploads/<uuid>/content/` with authorization-aware serving. Raster images are re-encoded to PNG; PDF attachments require appropriate access. Files are limited to 5 MiB and Nginx request bodies to 6 MiB. PDF signature checks are not malware scanning.

## Before launch

Complete the role-based acceptance checks in `docs/HANDOFF.md`, verify SMTP and the isolated runner, review the deployment checks and security test results, and arrange monitoring, patching, backups, and periodic security review. No software package can guarantee the absence of future bugs or attacks.

## Optional local sample data

Follow the [demo-only credentials and setup in the root README](../README.md#demo-only-admin-learner-and-instructor-accounts). Only in an isolated local environment, set **both** `DEBUG=true` and `ENABLE_DEMO_ACCOUNTS=true` in `.env`, recreate the API services, then explicitly run `docker compose exec api1 python manage.py seed_demo`. The production-oriented `scripts/validate-env.sh` intentionally rejects debug mode; use the root README's demo setup instead. Do not enable flags only on a one-shot seed container: the running API services need both flags to allow demo sign-in.

The command creates the three `demo.*@example.com` users and sample learning content. The exact public demo passwords are listed in the root README. Existing demo passwords are preserved unless `--reset-passwords` is explicitly passed; unrelated existing accounts are never claimed or promoted. Both flags default off, startup never seeds, and flagged demo accounts (including existing sessions) are denied if either flag is off. `DEMO_PASSWORD` is no longer used. Never seed a public production database.

Run regression tests with `docker compose exec api1 python manage.py test core` in a staging database account permitted to create a separate test database. Do not grant the production application broad database-creation privileges merely to run tests. For lightweight local checks, explicitly use `DEBUG=true DB_ENGINE=sqlite python manage.py test core`; MySQL is the deployment database.
