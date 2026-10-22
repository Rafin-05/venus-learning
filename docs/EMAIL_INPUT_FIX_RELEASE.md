# Signup recovery and malformed-input fixes

This update is based on `f6b6f70fb96ed2077bcdb5ba_venus-learning-panels-integrated.zip`, not the earlier rebuild. The integrated panel code and authorization changes are preserved.

## Fixed

Login and authenticated quiz submission now reject top-level JSON arrays with HTTP 400 and `{"detail":"Request body must be a JSON object."}`. The same guard rejects strings, numbers, booleans and null. Regression tests cover empty and populated top-level arrays, valid CSRF for login, no authentication/lockout side effects, and no quiz-attempt or points changes. Existing valid-object login and grading behavior remains covered.

A new `POST /api/auth/resend-verification/` endpoint and `/resend-verification` form let already-registered, unverified users request a fresh email. The form is linked from signup, sign-in and verification pages. Requests require CSRF, validate email, use generic confirmations for eligible and ineligible accounts, apply a 10-request source-IP limit per 15-minute window and a 60-second per-account cooldown, and issue single-use two-day links. Issuing a new link invalidates prior unused links. Mail exceptions roll back token changes, keep prior links usable, and log a generic warning without account or token details.

## Email delivery still needs deployment configuration

The release's local example environment intentionally uses Django's console email backend, so email is printed to API logs, not sent to inboxes. Configure real SMTP host, credentials, a provider-authorized sender, STARTTLS on a supported port such as 587, and the public HTTPS `FRONTEND_URL`, then recreate both API services. See [the email troubleshooting guide](EMAIL_TROUBLESHOOTING.md). No credentials or live deployment were changed, and no real-provider delivery is claimed.

## Validation

- Final backend run: **62 tests passed** using SQLite and Django's in-memory mail backend. Includes malformed-body, resend CSRF, privacy, cooldown, expiry, replacement, one-use, source-IP limit, and mail-failure rollback coverage.
- `python3 manage.py makemigrations --check --dry-run`: no changes detected; no new database migration is required.
- Shared frontend API-client tests: **9 passed**.
- `npm run build`: passed, including TypeScript validation and the `/resend-verification` route.
- The final modified backend was not retested with MySQL. The suite does not establish production concurrency behavior or real email deliverability.

Backend and frontend command output is included under `docs/verification/email-input-fix-backend.txt` and `docs/verification/email-input-fix-frontend.txt`. Older verification files describe the earlier integrated release and are retained for provenance.
