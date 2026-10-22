# Learner integration

The learner portal reads and writes shared backend records through `frontend/lib/api.ts`, using Django session cookies, fresh CSRF tokens for mutations, readable validation errors and complete paginated lists.

The dashboard and My Learning use `/auth/me/`, `/enrollments/` and `/certificates/`. Course discovery uses `/courses/`; course detail and public curriculum use the course detail/curriculum actions. Enrolled lesson viewing, progress, quizzes and certificates use `/lessons/`, lesson `progress` and `run` actions, `/quizzes/`, quiz `submit`, and course `certificate`. `/learn/[id]` and `/learning/[id]` connect to the learning experience.

Profiles use `/profile/`; uploads use `/uploads/`; issue reports and administrator responses use `/issues/`. Learners cannot edit their role, verification or privileges. Answer keys are removed by `QuizSerializer.to_representation`; coding problem test cases remain private.

Coding problems, submissions, contests, contest history and leaderboards are connected to `/problems/`, `/submissions/`, `/contests/`, `/contest-attempts/` and `/leaderboard/`, including their documented detail actions. Real coding execution requires an isolated Judge0-compatible runner configured by `JUDGE0_URL` or `CODING_RUNNER_URL`; without it the API returns 503 rather than fabricated grading. Contests enforce their server-side time window and one-attempt rule.

Authentication includes registration, mailbox verification, login, logout and password reset/change. Real verification and reset mail require configured SMTP. User-authored text renders as React text, not executable HTML.

See `../docs/PANEL_INTEGRATION.md` for final verification evidence and prerequisites.
