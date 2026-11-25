# Venus Learning API

All paths below are relative to `/api/`. JSON lists use `{count,next,previous,results}` pagination unless an action returns a small aggregate list. Browser mutations, including anonymous authentication forms and multipart uploads, require the CSRF cookie and `X-CSRFToken` header obtained from `GET /auth/csrf/` (`{csrfToken}`). Authentication uses same-origin Django session cookies, not browser local-storage tokens.

## Accounts

- `POST /auth/register/`: `{email,password,full_name,role}`; role is learner or instructor. Email format and password policy are validated. A one-use verification link expires after two days; instructors also need administrator approval.
- `POST /auth/resend-verification/`: `{email}`; CSRF-protected recovery for active, unverified accounts. Returns the same generic confirmation for valid email addresses regardless of account existence or eligibility. Source-IP limits and a per-account cooldown prevent repeated mail sends. Issued links expire after two days and replace previous unused verification links. Mail-provider failures preserve prior links and do not disclose account status. The user-facing form is `/resend-verification`.
- `POST /auth/login/`: `{email,password}`; generic failure messages and database-backed account/source-IP lockouts. `POST /auth/logout/` ends the current session.
- `GET/PATCH /auth/me/` or `/profile/`: read/edit safe profile fields. Role, email, privilege flags, counters, and verification state are not self-editable.
- `GET /auth/verify/<uuid>/`; `POST /auth/password-reset/` with `{email}`; `POST /auth/password-reset/confirm/<uuid>/` with `{password}`. Reset links expire after one hour and cannot be replayed.
- `POST /auth/change-password/`: `{current_password,new_password}`. Other sessions become invalid through Django's password/session hash, and the current API session is logged out.

Protected routes require a currently active, verified account; instructors must remain approved. Staff promotion is an explicit CLI/maintenance-administration operation, not a general REST user patch.

Registration, login, resend verification, password change/reset, profile update, lesson progress, coding lesson execution, quiz/contest submission, and problem submission require an object request body. Top-level JSON arrays, strings, numbers, booleans, and null are rejected with HTTP 400 and `{"detail":"Request body must be a JSON object."}` rather than causing server errors. Authentication, authorization and CSRF checks still apply. Malformed coding request bodies are rejected before submission throttling or runner calls, including when the problem runner is not configured.

## Courses and learning

Public `GET /courses/`, `/courses/<id>/`, `/courses/<id>/curriculum/`, and `/courses/<id>/reviews/` expose approved material only while its publisher remains active, verified, and approved. Public curriculum includes unit/lesson metadata, not private lesson bodies or answer keys. `?search=` and `?category=` filter the catalog; `?mine=1` selects an approved instructor's own draft/approved courses. Staff see moderation records.

Instructor-owner/staff CRUD uses `/courses/`, `/units/`, `/lessons/`, and `/quizzes/` (detail IDs for update/delete). Course changes by instructors require review. Course objects include `instructor_name`, `average_rating`, `student_count`, and `lesson_count`. `GET /courses/<id>/students/` is owner/staff-only.

Course creation (wizard, PDF §4) adds `subtitle`, `subcategory`, `language`, `level` (beginner/intermediate/advanced), `promo_video_url` (YouTube link; the server extracts `promo_provider_video_id`), `outcomes` (at most 20 strings), `target_audience`, `prerequisites`, `price`, `is_free` (a free course must have price 0; a paid course needs a price above 0), `enrollment_open`, `access_duration_days` (blank = no expiry), and `completion_threshold` (1–100, default 90). Lessons add `description`, `duration_seconds`, `is_preview`, `is_required`, and provider-neutral video fields `provider` / `provider_video_id`: a YouTube URL is validated on the server and its 11-character ID extracted; other HTTPS hosts are stored as `external`. Lesson types are video, document, coding, resource, quiz, and assignment. There is no live-class lesson type — live classes are not part of this feature.

`POST /courses/<id>/submit-review/` submits a draft for admin review (at least one section and one lesson are required) and records a `CourseReview`. `GET /courses/<id>/review-history/` lists the review audit trail for the owner/staff. `POST /courses/<id>/approve/` and `POST /courses/<id>/request-changes/` (notes required) are staff-only and record the decision; `PATCH /staff/courses/<id>/` with a status change is also audited. Enrollment is refused when `enrollment_open` is false, and paid courses cannot be enrolled in yet — payment collection is not built.

`GET /lessons/<id>/playback/` returns the embed identifier (`provider`, `provider_video_id`, `embed_url`) only after the backend confirms enrollment, ownership, or a free-preview lesson on an approved course. `PATCH /lessons/<id>/progress/` accepts `{watched_seconds,duration_seconds,resume_position_seconds}`: watched seconds are capped at the duration, never decrease, and replayed seconds are not double-counted; the lesson completes when `watch_percentage` reaches the course `completion_threshold`. A plain `{progress}` update keeps the previous self-reported behaviour for non-video lessons.

Resources: `GET/POST /resources/` (filter `?course=` / `?lesson=`), `GET /resources/<id>/download/`; a resource needs an uploaded `asset` or an `external_url`, not both, and only enrolled learners, the owner, or staff can download it. Deleting a resource attached to a published lesson needs `?confirm=1`.

Assignments: `GET/POST /assignments/` (filter `?course=`), `POST /assignment-submissions/` (file, text, or both per `accepted_types`; a late submission is marked `late`; resubmissions are new attempts, never overwrites), `POST /assignment-submissions/<id>/grade/` with `{score,feedback,status}` where status is `graded` or `needs_resubmission` and score cannot exceed `max_points`.

Quizzes can be linked to a lesson (`lesson`) and carry `time_limit_minutes`, `attempts_allowed` (null = unlimited; a further submit returns 409), `shuffle_questions`, `shuffle_options`, and `show_answers` (immediate/after_review/never).

Certificates require every *required* lesson at 100%, all course quizzes passed, and every *required* assignment graded. Course progress is completed required lessons / total required lessons.

Profiles: users have a `title` (professional title, editable on `/profile/` alongside full name, biography, expertise and profile picture; role, email, points and streak cannot be edited there). The profile picture is uploaded with `purpose=avatar` and stored as `profile_pic`. `GET /profile/summary/` returns role-aware data for the signed-in user: learners get enrollments with progress, certificates and upcoming mentor sessions; instructors get their courses, student total, average rating, review count, mentor profile and completed/upcoming sessions; admins get site counts. `GET /instructors/<id>/` returns the public profile of one approved instructor: public details, published courses with student counts and ratings, totals, mentor profile and completed sessions; it is 404 for anyone who is not an approved instructor. There is no separate achievements model — points, streak and certificates are the learner record shown on the profile.

`GET/POST /courses/<id>/enroll/` reads or idempotently creates a learner enrollment. `GET /enrollments/` returns the current learner's nested courses and progress. Enrolled learners can read lessons (`?course=<id>` supported), update 0–100 progress with `PATCH /lessons/<id>/progress/`, and submit quizzes. Learners cannot self-attest coding completion; non-coding progress is learner-attested.

Quiz writes include nested questions with `question,option_a,option_b,option_c,option_d,correct_answer`. Question rewrites invalidate prior attempts. `POST /quizzes/<id>/submit/` takes `{answers:{"<question-id>":"a"}}` and grades on the server. Learner responses hide answer keys and stored answer payloads. `GET /quiz-attempts/` returns the current learner's history.

`POST /ratings/` creates a review; `PATCH /ratings/<id>/` edits the learner's own review. Enrollment in a currently published course is required. `GET /ratings/?course=<id>` is user/owner-scoped. Public review reads use the course reviews action.

`POST /courses/<id>/certificate/` requires every lesson (including coding) at 100% and all course quizzes passed; issuance is idempotent. `GET /certificates/` returns the learner's named, numbered certificates with nested course/instructor metadata.

## Files

`POST /uploads/` uses multipart `file,purpose,course` (`course` is omitted for avatars). Purposes are `avatar`, `thumbnail`, and `document`; course assets require the owning approved instructor or staff. Response: `{id,url,purpose}`. Files are at most 5 MiB. JPEG/PNG/WEBP images are dimension-bounded, decoded and re-encoded to PNG without original metadata. Documents must have a PDF signature and are attachment downloads, not inline HTML.

`GET /uploads/<uuid>/content/` authorizes access. Active verified avatars and currently approved course thumbnails can be public; documents require owner/staff or an active verified learner enrolled in the published course. Direct `/media/` is blocked by Nginx. Changing an instructor thumbnail returns the course to pending review.

## Coding

Owner/staff manage `/problems/`; problem writes include private `test_cases:[{input,output}]`. `POST /problems/<id>/submit/` and `/lessons/<id>/run/` accept `{code,language_id}`. The allowlist is Python 71, JavaScript 63, Java 62, C++ 54, C 50, Go 60, and Rust 73. A configured isolated Judge0-compatible service performs execution; every problem test case is checked and points are awarded once per learner/problem. Source/runtime/output are bounded. Provider failure or no configured runner returns 503 and never awards completion. `GET /submissions/` is user-scoped.

## Contests, rankings and support

Staff manage `/contests/` with `title,description,starts_at,ends_at,prize,prizes,questions`. Ranked prizes use `[{position:1,prize_label:"First prize"}]` with unique numeric ranks. Question IDs are unique and choices use a–d. The server enforces `start <= now < end`, grades learner submissions, and permits one attempt per learner; duplicates return 409. Upcoming questions and live answer keys are hidden from learners. Recorded contests cannot have their question/window edited.

Every supplied `option_a` through `option_d` must be a string of at most 1000 characters. Options a/b are required and must not be blank; c/d may be omitted or empty strings. The correct answer must select a nonblank option. Objects, arrays, numbers, booleans, null, and oversized values are rejected on both creation and update rather than persisted and returned to learners.

`POST /contests/<id>/submit/` takes `{answers:{"<question-id>":"a"}}`. `GET /contests/<id>/leaderboard/`, `/contest-attempts/`, `/leaderboard/`, and `/dashboard/` provide scoped real results/counts. Contest standings expose ranked prize labels after the contest ends.

`GET/POST /issues/` provides the user's reports. Staff update responses/status via `/staff/issues/<id>/` (or the staff-authorized issues detail route). `/staff/users/`, `/staff/courses/`, and `/staff/dashboard/` are staff-only moderation routes. User mutations are whitelisted; unknown privilege fields are rejected.

All authored text is plain text and serialized URLs accept HTTP(S) only. Error responses use DRF validation format. See automated tests for permission and malformed-input examples.
