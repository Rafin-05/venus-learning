# Venus Learning: developer handoff

## Ready for the receiving developer

This ZIP is the rebuilt source project, not a public deployment. It replaces the supplied PHP application with Next.js + TypeScript, Django REST Framework, and MySQL. Nginx routes the frontend and balances API traffic across two replicas. The original supplied logo is retained in `frontend/public/venus-logo.png`; `venus-wordmark.png` trims only its blank margins for display.

Start with the root README and `deploy/README.md`. Do not run the old PHP installation or import its default administrator credentials.

## Working feature map

| Original capability | Rebuilt location |
|---|---|
| Registration, login, verification, reset, profile | `/register`, `/login`, `/verify/<token>`, `/reset`, `/reset/<token>`, `/profile` |
| Catalog, course detail and reviews | `/courses`, `/courses/<id>` |
| Enrollment, learning progress, lessons and quizzes | `/my-learning`, `/learning/<id>`; `/learn/<id>` remains an alias |
| Coding lessons and standalone problems | Learning workspace; `/coding-problems`, `/coding-problems/<id>`, `/submissions` |
| Timed MCQ contests, prizes, results and history | `/contests`, `/contests/<id>`, `/leaderboard?contest=<id>`, `/contest-history` |
| Certificates | `/certificates`; named, numbered certificates print individually |
| Instructor authoring | `/instructor`, `/instructor/courses`, `/instructor/courses/new`, `/instructor/courses/<id>`, `/instructor/quizzes` |
| Administrative moderation | `/admin`, `/admin/courses`, `/admin/instructors`, `/admin/users`, `/admin/quizzes`, `/admin/problems`, `/admin/contests`, `/admin/issues` |
| Reports and replies | `/report-issue`; staff reply/status controls in `/admin/issues` |
| Avatars, thumbnails and lesson documents | Multipart `/api/uploads/`; PNG/JPEG/WEBP input and PDF downloads |

The platform uses one account model with explicit learner/instructor/admin roles, rather than separate insecure PHP login systems. Instructor accounts require email verification and approval. Course edits, curriculum changes, quizzes, and instructor thumbnail changes send a course back for review. Revoked, unverified, or blocked publishers lose public course visibility and learner content access.

## Important behavior

Coding is a real integration boundary: configure an independently isolated Judge0-compatible runner. Without one, submissions return HTTP 503 and never receive a successful grade. The web servers never execute learner programs. Runner tests are mocked; a real provider was not connected or charged.

Course content and reviews are plain text. No legacy rich HTML, arbitrary embedded scripts, PHP, SVG uploads, or third-party form widgets are carried into the new site. YouTube URLs use the embedded privacy-enhanced player; other HTTP(S) video URLs open as external links. Document uploads are PDFs and are served as downloads only to authorized users. Raster images are decoded, bounded, and re-encoded to fresh PNG bytes without their original metadata. The 5 MiB upload limit and image-dimension limits are intentional.

PDF signature checks and forced download are not an antivirus service or proof a document is harmless in every PDF reader. Add malware scanning and an upload-retention policy if required for the target audience.

Quiz question rewrites replace question IDs and invalidate prior quiz attempts. Review curriculum changes carefully on a live course; retain a database backup and communicate changed completion requirements. Contests with submissions cannot have their question set or time window edited. Prizes are rank/label metadata, not automated payments.

## Before public launch

1. Supply the real domain, TLS certificate/renewal process, unique secrets, and allowed hosts/origins.
2. Configure and test SMTP delivery, including spam-folder behavior and reset/verification links.
3. Connect and security-review the isolated coding runner if coding execution is required.
4. Build and exercise the Docker images on the target host. Both Compose configurations were validated, but a Docker daemon was not available for container-image execution here.
5. Restrict `/django-admin/` to trusted operators/VPN where possible. Create administrators explicitly with `createsuperuser`; there is no bundled administrator password.
6. Configure backups and test restores, monitoring, log access/retention, dependency/image patching, and incident procedures. Expire old email tokens, upload orphans, and sessions through an operator-controlled retention process.
7. Run the supplied tests and smoke checks against staging. Perform browser acceptance testing with real roles, mobile devices, actual video hosting, actual email, and the configured runner before inviting learners.

API load balancing was exercised locally against two Gunicorn instances sharing MySQL. This is single-host application-tier balancing, not multi-host high availability. No package can promise that every unknown future bug or attack has been eliminated.
