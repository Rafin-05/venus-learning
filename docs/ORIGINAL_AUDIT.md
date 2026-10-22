# Original LearnSpace inventory and security audit

This is an inventory of the files in `venus-original/learnspace`; it is not a claim that the new Django/API implementation is complete.

## Route and feature inventory

| Area | Existing PHP routes | Observed capability |
|---|---|---|
| Learner | `dashboard.php`, `courses.php`, `course-detail.php`, `course-learn.php`, `my-learning.php`, `profile.php`, registration/login/logout, certificates, quiz, coding problems, contests, leaderboard, reports | Browsing/enrollment/progress, quizzes, certificates, coding exercises, contest participation and support messages |
| Instructor | dashboard, register/login/logout, add-course, add-quiz, course-view, my-courses, profile, report-issue | Course and quiz authoring/management |
| Admin | dashboard/login/logout, courses/course-action/course-detail/pending/remove, users, instructors, quizzes, coding problems, contests/results/history, leaderboard, messages | Administrative moderation and reporting |
| AJAX | `update-progress.php`, `submit-rating.php`, `execute-code.php`, `execute-problem.php` | Progress, ratings, and remote code-execution submissions |

The contest implementation is **MCQ questions plus prizes and participant results**; the source does not establish a general multiplayer contest engine. The rebuild maps these as timed MCQ contests; see the final handoff and verification record for implementation status.

The SQL schema declares entities for admins, users, instructors, courses, units, lessons, enrollments, lesson/unit completions, ratings, certificates, quizzes/questions/attempts, contests/questions/participants/prizes, support messages, coding problems and problem completions. No original dump data or credentials are reproduced here.

## Material security risks observed

- `includes/db.php` hard-codes a local `root` database account with an empty password. The replacement uses Compose-injected secrets and does not publish MySQL.
- Multiple pages interpolate numeric request parameters into SQL strings. Some writes use prepared statements, but the codebase is inconsistent; authorization and input validation need endpoint-by-endpoint review.
- Session-based forms and AJAX handlers do not show a consistent CSRF strategy in the inspected files. The new deployment must keep Django CSRF enabled and use same-origin requests.
- `execute-code.php` sends learner source code to a third-party Judge0 endpoint. This is an external data/code disclosure and remote execution dependency; no external judge is enabled by this deployment by default. If restored, isolate, authenticate, rate-limit, cap source/runtime/output, and allowlist languages.
- Error handling can disclose database connection errors, and the original login/database setup contains credential-sensitive fields. Secrets must remain in `.env`/secret storage and never in committed audit artifacts.
- User profile/email and learning records are personal data. The replacement keeps DB/Redis internal, blocks public `/media/`, and requires authenticated API download handling for private uploads.
- The original pages load third-party scripts (for example Jotform embed). The replacement uses a per-request nonce-based Next.js script CSP and omits the legacy third-party widget; inline styles remain allowed.

## Mapping status

This document describes source behavior only. It does not certify feature parity, migration correctness, authorization correctness, or production readiness of Venus Learning. Validate each route against the implemented Django API and frontend before declaring it shipped.
