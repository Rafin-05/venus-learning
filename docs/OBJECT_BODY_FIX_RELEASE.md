# Request-body and contest-option fixes

This update starts from `2451852bcaddde60ae30760b_venus-learning-panels-integrated-password-input-fixed.zip`. It preserves the Venus Learning branding, existing stack, prior malformed-input fixes, and verification-email resend flow. It does not change dependencies or database schema.

## Five endpoints now reject non-object JSON

The existing object-body guard now protects:

- `PATCH /api/auth/me/` (also the existing profile alias)
- `PATCH /api/lessons/<id>/progress/`
- `POST /api/contests/<id>/submit/`
- `POST /api/lessons/<id>/run/`
- `POST /api/problems/<id>/submit/`

Arrays, strings, numbers, booleans and null return HTTP 400 with `{"detail":"Request body must be a JSON object."}`. Coding request guards run before throttling or runner execution. Problem submission also validates the body when no runner is configured; valid object requests still receive the existing HTTP 503 for an unavailable runner. Authentication, authorization, and CSRF checks remain enforced.

Eight tests in `backend/core/test_object_body_input.py` exercise empty and populated arrays, strings, integers, decimals, both booleans, and null with real session authentication and valid CSRF. They verify unchanged users, enrollments, progress, attempts, submissions, completions, activity, certificates, throttle records, and session identity, plus no throttle/runner calls on rejected bodies. They also cover missing authentication/CSRF and valid profile, progress, contest, coding lesson, and problem workflows. Runner success is mocked, not executed externally.

Before the endpoint guards were applied, these eight tests failed with 22 unhandled-error subcases and 26 assertion-failure subcases. After the fix, all eight passed.

## Contest choices are bounded strings

`ContestSerializer` validates every supplied `option_a`–`option_d` as an actual string of at most 1000 characters, consistent with quiz option limits. Required a/b choices must be nonblank. Optional c/d choices can be absent or empty strings; whichever choice is marked correct must be nonblank. Null, objects, arrays, numbers, booleans, and oversized values are rejected on both create and update. Validation prevents newly written malformed option values from reaching learner rendering; this release does not migrate previously stored malformed contest data.

Four additional tests in `backend/core/test_contest_option_input.py` cover invalid values for each choice on create/update, maximum-length acceptance, blank options, learner string responses, and hidden answer keys. Frontend text rendering and escaping remain unchanged.

## Checks passed

- Full backend suite: **79 tests passed on MySQL 8.0.46**, including all 12 new tests and existing authentication, permissions, email recovery, and malformed-input regressions.
- Django system check: no issues.
- Migration drift check: no changes detected.
- Shared frontend API-client suite: **9 tests passed**.

Logs: [MySQL backend checks](verification/object-body-fix-backend-mysql.txt) and [frontend API-client checks](verification/object-body-fix-frontend.txt). Tests used local in-memory email delivery, not real SMTP. Frontend source is unchanged, so its production build was not rerun. This is an updated source package, not a public deployment or a claim that all future bugs are eliminated.

## Package integrity

`RELEASE_MANIFEST.sha256` lists every released file except itself. The archive omits installed dependencies, build output, Python caches, local databases, runtime environment files, and credentials. Existing release documents and verification logs are retained as historical records; this note describes the current follow-up.
