# Venus Learning: panels integrated and verified

The administrator, instructor and learner panels use one Django REST API and the same MySQL records. The completed source is based exclusively on the delivered `693af286d607fa885e07fee0_venus-learning-final.zip`, not the earlier Learnspace archive.

## What was fixed

- Replaced the instructor overview's demo counts and sample courses with authenticated dashboard metrics and owned courses from the shared API.
- Added the backend-supported **resolved** status to administrator support handling.
- Made the staff dashboard and staff users/courses/issues endpoints explicitly staff-only. Previously the staff dashboard URL could return a non-staff user's own dashboard, and other staff lists relied on empty querysets rather than explicit permission denial. No administrator data exposure was observed from that dashboard alias.
- Consolidated avatar, course-thumbnail and document uploads through the same CSRF-aware API client used by the panels.
- Updated older integration notes that incorrectly described already-implemented unit, quiz, coding and contest routes as unfinished.
- Added cross-panel backend tests, shared-client tests and a repeatable live HTTP workflow script.

The existing learner route payloads and endpoint paths matched the backend and did not require source changes. The supplied wordmark is preserved byte-for-byte at `frontend/public/venus-wordmark-original.png`; the existing tightly cropped version remains the visible navigation/footer wordmark.

## Verified shared workflow

A live evaluation stack used the production Next.js build, Nginx, two Gunicorn API replicas and a new MySQL database. Separate cookie-authenticated administrator, instructor and learner sessions successfully exercised:

1. Instructor course, unit, lesson and quiz creation.
2. Administrator discovery of the same pending course and approval for publication.
3. Learner discovery and enrollment, reflected in the instructor's student roster.
4. Saved lesson completion, server-graded quiz submission and certificate issuance.
5. Learner denial from staff APIs and moderation actions.
6. Learner issue creation and administrator response, visible to that learner.
7. Repeated session reads through the load-balanced API replicas.

Private evaluation accounts, database data, runtime secrets and cookies are not included in the release ZIP. The live journey creates test records and must be run only in an isolated evaluation deployment.

## Verification results

| Check | Result | Evidence |
|---|---|---|
| Full Django suite on MySQL 8.0.46 | **53 tests passed** | [MySQL test log](verification/panel-integration/mysql-tests.txt) |
| Shared TypeScript API client | **9 tests passed** | [Client test log](verification/panel-integration/shared-client-tests.txt) |
| Production frontend build | **Passed** | [Build log](verification/panel-integration/frontend-production-build.txt) |
| TypeScript checking | **Passed** | [Typecheck log](verification/panel-integration/typecheck-final.txt) |
| Nginx/full-stack smoke | **12 checks passed** | [Smoke log](verification/panel-integration/full-stack-smoke.txt) |
| Three-role live HTTP workflow | **Passed** | [Journey log](verification/panel-integration/live-panel-journey.txt) |

Browser inspection also confirmed that anonymous visits to `/admin`, `/instructor` and `/dashboard` show the sign-in gate; no browser console errors were observed on the learner gate. Authenticated mutations were verified through real HTTP sessions, not a complete interactive browser click-through of every screen. Nginx access logs confirmed requests reached both API replicas.

## Security checks

Existing and new regression tests passed for email-format validation, one-use mailbox-verification links, CSRF, password reset expiry/replay, account lockout/brute-force filtering, rejection of JavaScript URLs, private quiz answer keys, privilege-edit rejection, cross-instructor isolation and SQL-injection search treated as literal input. Production smoke checks confirmed nonce-based script CSP, MIME-sniffing/framing protection, blocked raw media and blocked dotfiles. React text escaping, validated links and parameterized Django ORM queries remain the XSS and SQL-injection defenses; these are layered controls, not a claim of perfect security.

## Running and deploying

From `frontend/`, run `npm ci`, `npm run test:api`, `npm run build` and `npm run typecheck`. From `backend/`, use the documented database environment and run `python manage.py test --noinput`. The new live workflow is `python scripts/panel_http_journey.py`; supply `BASE_URL` and `PANEL_{ADMIN,INSTRUCTOR,LEARNER}_{EMAIL,PASSWORD}` through the environment using isolated verified test accounts. The instructor account must be approved to sign in.

The target stack remains **Next.js + TypeScript, Django REST Framework, MySQL and Nginx**. The supplied Compose deployment targets MySQL 8.4; this verification used installed native services with MySQL 8.0.46, not a fresh Docker Compose deployment. See [deployment instructions](../deploy/README.md) for production setup.

This is a verified source handoff, not a public production launch. Real deployment still requires a domain, HTTPS certificates, private secrets, SMTP for mailbox verification/password reset, database backups and an isolated Judge0-compatible runner for real coding execution. Without a configured runner, coding requests correctly return 503 rather than pretend to grade submissions.
