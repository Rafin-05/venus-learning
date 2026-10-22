# Verification record

## Passed

| Check | Result |
|---|---|
| Fresh schema and regression suite on real MySQL | 50 tests passed; MySQL 8.0.46 |
| TypeScript strict checks | Passed |
| Next.js production build | Passed with Next.js 16.4.2 and React 19.3.1 |
| Full-stack smoke tests | 14 checks passed |
| API load balancing | Nginx reached both real Gunicorn API replicas; authenticated sessions survived repeated requests |
| Native user journey | Authoring, approval, enrollment, private PDF download, progress, quiz grading, named certificate, review, support response, avatar upload, and contest submission passed |
| Unconfigured coding runner | Returned HTTP 503 without awarding a successful result |
| HTTP and HTTPS Nginx templates | Syntax validated with local upstream/path substitutions; HTTPS check used a temporary local self-signed certificate |
| Compose base and HTTPS override | Both resolved successfully with Compose validation |
| Environment validation | Placeholder secrets rejected; distinct non-placeholder evaluation values accepted |
| Frontend dependency audit | No known vulnerabilities reported by npm audit |
| Python dependency audit | No known vulnerabilities reported by pip-audit for the pinned requirements |
| Browser inspection | Public catalog and course detail loaded with supplied branding; no console errors in the checked catalog session |

Raw non-sensitive output is included in `verification/`. Runtime environments, database contents, credentials, cookie jars, email tokens, and temporary TLS keys are deliberately excluded.

## Regression coverage

The 50 tests exercise anonymous CSRF rejection, email/password policy, verification/reset expiry and replay, account lockouts surviving IP changes, blocked/unverified/unapproved accounts, cross-owner CRUD denials, pending-course access, revoked publisher visibility, enrollment checks, literal SQL-injection search input, unsafe URL rejection, privilege-field rejection, answer-key redaction, malformed numeric/answer payloads, nested quiz authoring, server grading, coding completion, all-test-case runner grading, one-time problem awards, certificate eligibility/idempotency, ratings, staff moderation, unique contest submissions, ranked prize validation, user-scoped histories, multipart CSRF, upload type/size/ownership checks, PNG byte conversion/metadata stripping, thumbnail reapproval, and private PDF access.

The fast MD5 password hasher is explicitly scoped to automated test fixtures only. Runtime password hashing remains Django's normal secure configuration. The production-like native stack ran with DEBUG=false and a dedicated application database account; test database creation used a separate local test connection.

## What these checks do not establish

The local integration stack used native processes: production Next.js, Nginx, two Gunicorn instances, and MySQL. Docker Compose configuration was validated, but container images were not built/run under a Docker daemon. The Compose target specifies MySQL 8.4; the available native MySQL tested here was 8.0.46.

No public deployment/domain was provisioned. Real SMTP delivery, a real external code-execution provider, real legacy-data import, complete authenticated browser automation, mobile-device acceptance, accessibility certification, load/concurrency stress testing, antivirus scanning, penetration testing, and OS/container-image vulnerability scans were not performed. Mocked runner tests establish application grading/error behavior, not the security or availability of a future execution provider.

Passing tests and clean known-vulnerability audits are evidence for this source handoff, not a guarantee against every present or future defect. Use `HANDOFF.md` and the deployment guide for launch acceptance.
