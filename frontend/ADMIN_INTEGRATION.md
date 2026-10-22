# Admin integration

Admin pages use the shared `frontend/lib/api.ts` request helper (session cookie + CSRF) and render API errors instead of swallowing them. `PortalShell` is responsible for the `Admin` role gate; the pages do not duplicate authorization.

## Routes used

| Page | Read | Mutations |
|---|---|---|
| `/admin/courses` | `GET /api/staff/courses/` | `PATCH/DELETE /api/staff/courses/:id/` with `status: pending|approved|rejected` |
| `/admin/users` | `GET /api/staff/users/` | `PATCH /api/staff/users/:id/` with `is_active` |
| `/admin/instructors` | `GET /api/staff/users/` | `PATCH /api/staff/users/:id/` with `instructor_approved` or `is_active` |
| `/admin/problems` | `GET /api/problems/` | `POST/PATCH/DELETE /api/problems/:id/` |
| `/admin/contests` | `GET /api/contests/` | `POST/PATCH/DELETE /api/contests/:id/` |
| `/admin/issues` | `GET /api/staff/issues/` | `PATCH /api/staff/issues/:id/` with `response` and `status` |

Problem `test_cases` and contest `questions` are JSON editors with templates. They are parsed and validated as arrays before submission; they are never posted as JSON strings. Contest `correct_answer` must be `a`, `b`, `c`, or `d`. `datetime-local` values are interpreted in the administrator's browser timezone and converted to ISO UTC strings before submission; the table displays the server's ISO values.

## Backend assumptions / residual limitations

- The delivered staff user serializer exposes writable `is_active` and `instructor_approved` booleans. Credential, verification and privilege changes are rejected by this endpoint.
- Support status options are `open`, `in_progress`, `resolved`, and `closed`; the API remains authoritative.
- Backend authorization remains authoritative. Delete buttons may still return a visible authorization or validation error.
- No synthetic dashboard statistics are shown; the overview counts only loaded API data.
