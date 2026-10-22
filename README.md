# Venus Learning

A rebuild of the supplied LearnSpace PHP application using **Next.js and TypeScript**, **Django REST Framework**, and **MySQL**, served through an **Nginx API load balancer**. The supplied Venus Learning wordmark replaces the old branding.

This is a source-code handoff, not a deployment to a public server. Start with [the deployment guide](deploy/README.md), [the API contract](backend/API_CONTRACT.md), and [the verification record](docs/TEST_RESULTS.md).

This update adds opt-in, local-only demo accounts for all three roles, with fixed public test credentials and production authentication/session lockout. See [demo setup below](#demo-only-admin-learner-and-instructor-accounts). No accounts or database are bundled or created automatically.

The preceding follow-up fixes five remaining non-object request-body failures and validates all contest options as bounded strings. See [the request-body and contest-option release notes](docs/OBJECT_BODY_FIX_RELEASE.md): all 79 MySQL-backed backend tests and 9 frontend API-client tests passed. Prior malformed-input fixes and verification-email recovery are preserved.

The delivered final ZIP has received an additional panel integration pass. See [the final panel fixes and verification](docs/PANEL_INTEGRATION.md): 53 MySQL-backed backend tests, 9 shared-client tests, the production build and a live administrator/instructor/learner workflow passed.

## What is included

The application has learner, instructor, and administrator workflows: course discovery, curriculum authoring and approval, enrollment, learning progress, quizzes, coding exercises, contests, rankings, certificates, profile management, and issue reporting. See [the feature and security audit](docs/ORIGINAL_AUDIT.md) for the original application inventory and [the handoff notes](docs/HANDOFF.md) for implementation boundaries.

The frontend communicates with the API on the same origin using session cookies and CSRF protection. Data lives in MySQL; API replicas share the database and cache. Nginx routes API requests to two backend services. This is application-tier load balancing on one Docker host, not a multi-host highly available database or a promise of zero downtime.

## Start safely

1. Install Docker Engine and the Docker Compose plugin on the target host.
2. Copy `.env.example` to `.env` and replace every secret placeholder. Use separate random database and Django secrets; do not use the legacy application's default administrator password.
3. Follow `deploy/README.md` to build the services and run migrations. Create your administrator explicitly; none is supplied with a default password.
4. For public use, configure your actual domain, HTTPS certificates, trusted origins, SMTP, and secure cookies before allowing registrations.
5. Configure a separately isolated Judge0-compatible runner if coding submissions are needed. The website must not execute submitted programs on its own application or database server.

The default local setup is intended for local HTTP evaluation only. Do not publish it unchanged. A TLS configuration template is supplied for production setup.

## Demo-only admin, learner, and instructor accounts

These are **public, deliberately shared test credentials**, not production accounts. Nothing is created on startup or by migrations. Seeding and signing in with demo accounts both require `DEBUG=true` **and** `ENABLE_DEMO_ACCOUNTS=true`; both flags default to false. The default Compose HTTP port binds to `127.0.0.1` only. Do not expose demo mode publicly or point it at a production database.

The sign-in username is the **email address**:

| Role | Email / username | Demo-only password | Landing page |
| --- | --- | --- | --- |
| Admin | `demo.admin@example.com` | `VenusDemo-Admin-2026!` | `/admin` |
| Learner | `demo.learner@example.com` | `VenusDemo-Learner-2026!` | `/dashboard` |
| Instructor | `demo.instructor@example.com` | `VenusDemo-Instructor-2026!` | `/instructor` |

### Local setup with Docker

1. Install Docker Engine and Compose plugin 2.24.4 or newer. Extract this ZIP and open a terminal in `venus-learning/`.
2. Copy `.env.example` to `.env`. Replace `DJANGO_SECRET_KEY` with at least 50 random characters, and replace the two database password placeholders with different random values. These deployment secrets are separate from the public demo passwords above.
3. For this **isolated local demo only**, set `DEBUG=true` and `ENABLE_DEMO_ACCOUNTS=true` in `.env`. Keep the local HTTP cookie/redirect settings from the example. Do not use `compose.production.yaml` for a demo; it intentionally forces demo mode off. `scripts/validate-env.sh` is the production-oriented validator and rejects debug mode.
4. Build, start, and explicitly seed:

   ```sh
   docker compose up -d --build
   docker compose logs init
   # Wait until migrations finish and both API services are healthy.
   docker compose exec api1 python manage.py seed_demo
   ```

5. Open **http://localhost:8080/login**, enter one of the exact email/password pairs above, and sign in. No email link is needed: demo users are already verified, the instructor is approved, and the demo admin has staff/superuser access. Use a separate browser profile for each role, or sign out before switching roles. The optional Django maintenance login is `http://localhost:8080/django-admin/` (admin credentials only).

The seed also creates sample courses, lessons, quizzes, a coding problem, and a contest. Coding execution still requires a separately configured runner. Re-running the command does not duplicate sample data or overwrite changed passwords. To explicitly restore the three documented demo passwords:

```sh
docker compose exec api1 python manage.py seed_demo --reset-passwords
```

The command refuses to take over an existing non-demo account with a matching email or an unexpected role. Use a separate local database if it reports a collision; do not delete real users to make room.

### Turn demo access off / prepare for production

Set `ENABLE_DEMO_ACCOUNTS=false` and `DEBUG=false`, then recreate **both** API services with `docker compose up -d --force-recreate api1 api2`. Removing the flag alone from a running container does not change its environment. Flagged demo accounts can no longer authenticate or use existing sessions once either flag is off. Normal accounts are unaffected.

The production override forces **both flags false** for `api1`, `api2`, and the `init` job, even if the local `.env` enables them. Demo users carry a persistent `is_demo_account` marker, so moving a seeded database does not silently turn these shared logins into production logins. Nevertheless, use a **fresh production database**, never reuse local demo volumes, and create a real administrator with `createsuperuser`. Do not change demo markers or grant demo identities real access. These guards do not make `DEBUG=true` safe for public deployment.

### Verification for this update

All **87 backend tests passed against MySQL**, including 8 demo-account tests covering all three API logins, administrator access boundaries, opt-out and production guards, existing session rejection, real-account compatibility, collision rollback, idempotence, password hashing, and explicit reset. `makemigrations --check --dry-run` found no missing migrations. All **9 shared frontend API-client tests passed**. Logs: [backend](docs/verification/demo-accounts-backend-mysql.txt) and [frontend](docs/verification/demo-accounts-frontend.txt). The Compose files were parsed and production demo-off overrides checked; Docker is unavailable in this verification environment, so this update's container startup was not re-run. No frontend source changed, and no public deployment was made.

## Security, without misleading guarantees

Email format validation and a mailbox-verification flow address different problems: a well-formed address is not proof that a person owns its mailbox. SMTP must work for verification and password reset to work in a real deployment.

XSS defenses rely on plain-text content, React escaping, validated links, and browser security headers. SQL injection defenses rely on parameterized Django ORM queries, not a blacklist of suspicious words. Login throttling and edge request limits reduce brute-force attempts; they do not make credential theft or distributed attacks impossible.

Security controls need correct deployment, dependency updates, monitoring, and ongoing testing. This package does not claim that all possible present or future defects have been eliminated. Identified issues and the tests actually run are recorded in the handoff documents.

Reference guidance: [Django security](https://docs.djangoproject.com/en/5.2/topics/security/) and [OWASP authentication and login throttling](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

## Existing data

The supplied `database.sql` contains table definitions and an insecure default administrator insert, but no learner accounts, course rows, enrollments, or historical results to transfer. The old SQL dump and Git history are intentionally not included in this package. A live site's data is not available from the supplied archive; see [migration notes](docs/MIGRATION.md) before connecting any real legacy database.

## Project layout

- `frontend/`: Next.js application, TypeScript source, supplied branding and reusable original imagery.
- `backend/`: Django models, REST API, migrations, automated tests, and administration.
- `deploy/`: Nginx routing and deployment documentation.
- `scripts/`: environment and smoke-test helpers.
- `docs/`: original-system audit, migration considerations, verification results, and handoff notes.
- `compose.yaml` and `compose.production.yaml`: container orchestration and HTTPS deployment override.

Use the lockfiles and dependency versions included with the project. No `.env`, installed dependencies, live database, session cookies, email tokens, or production credentials belong in the release ZIP.
