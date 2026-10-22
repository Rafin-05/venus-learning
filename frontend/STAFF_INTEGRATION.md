# Staff integration

All panels use same-origin `/api/` requests, Django sessions, CSRF tokens and the shared `frontend/lib/api.ts` client. `PortalShell` gates the visible workspace; the backend independently authorizes each operation.

The instructor overview loads real counts from `/dashboard/` and recent owned courses from `/courses/?mine=1`. Course authoring uses `/courses/`, `/units/`, `/lessons/` and `/quizzes/`; these routes are implemented in the delivered backend. Instructor edits return affected courses to pending review. Student rosters and reviews use the course `students` and `reviews` actions. Asset uploads use the same shared CSRF-aware client.

Administrators moderate courses through `/staff/courses/`, approve/block instructors through `/staff/users/`, and respond to reports through `/staff/issues/`. Public account self-editing cannot promote a role, verify an email or grant staff privileges. Administrative role promotion remains an explicit operator task.

Coding problem and contest authoring send parsed JSON objects and arrays, not JSON strings. Quiz answers remain private to course owners and administrators. Support statuses are `open`, `in_progress`, `resolved` and `closed`.

See `../docs/PANEL_INTEGRATION.md` for final fixes, verification evidence and deployment prerequisites.
