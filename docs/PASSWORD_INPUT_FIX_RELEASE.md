# Password request validation fix

Password change and both password-reset routes now reject top-level JSON arrays with HTTP 400 instead of crashing. They use the existing response:

```json
{"detail": "Request body must be a JSON object."}
```

The same validation rejects strings, numbers, booleans and null. Object-shaped requests retain their existing behavior.

## What changed

The existing `require_object_body(request)` guard now runs at the beginning of `ChangePasswordView.post` and `PasswordResetView.post`. For reset requests it runs before throttling, token lookup or email delivery. Routes, authentication, CSRF protection and password validation are unchanged. No database migration is needed.

Five regression tests in `backend/core/test_password_input.py` cover empty and populated arrays plus other non-object JSON on:

- `/api/auth/change-password/`
- `/api/auth/password-reset/`
- `/api/auth/password-reset/confirm/<token>/`

The tests use valid CSRF and a real authenticated session where required. Rejected bodies leave passwords, sessions, existing tokens and throttle records unchanged, and send no email. Tests also confirm that a reset token remains usable afterward, a valid password change still updates the password and logs the user out, and malformed bodies cannot bypass authentication or CSRF.

## Checks passed

- Before the fix, the new regression suite reproduced 18 unhandled exceptions across the three routes (six malformed payloads each).
- After the fix, all **5 new regression tests passed**.
- The full backend suite passed: **67 tests**, using SQLite and the in-memory email backend.
- Django system check: no issues.
- Migration drift check: no changes detected.
- Shared frontend API-client tests: **9 passed**, using the globally installed TypeScript dependency via `NODE_PATH="$(npm root -g)" npm run test:api`.

Command output is saved in `docs/verification/password-input-fix-backend.txt` and `docs/verification/password-input-fix-frontend.txt`. The frontend source was unchanged; its production build was not rerun. MySQL and real-provider email delivery were not tested in this follow-up.

## Existing email recovery is preserved

This follow-up starts from `365efd53c9116ede0e53f468_venus-learning-panels-integrated-email-input-fixed.zip` and preserves its login/quiz array guards and verification-email resend flow. It does not change deployment credentials or mail-provider settings. Missing signup emails still require correct SMTP configuration; see [Email troubleshooting](EMAIL_TROUBLESHOOTING.md). Earlier release notes and verification logs are retained as historical evidence.
