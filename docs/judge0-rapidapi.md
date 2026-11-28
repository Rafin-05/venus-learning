# Coding challenges — Judge0 via RapidAPI

Coding challenges already exist in Venus Learning: instructors create Problems
with test cases, learners submit code from `/coding-problems`, and the backend
grades each submission against the test cases (+10 points on first pass).
Lesson coding exercises (`/api/lessons/<id>/run/`) use the same runner.

The runner itself is Judge0, reached over HTTP. Until this is configured,
every submission answers **503 "The isolated code runner is not configured."**

## Setup (RapidAPI)

1. Go to https://rapidapi.com/judge0-official/api/judge0-ce and subscribe to a
   plan. Check the plan shown at subscribe time: older guides mention a free
   50–100 submissions/day tier, but recent checks (Nov 2026) show the Basic
   plan as pay-per-submission ($0.0017 each) and the Pro plan at $44.99/month
   for 2,000/day. Pick the plan whose daily limit fits the class.
2. Copy your RapidAPI key from the RapidAPI dashboard.
3. In the project's `.env` (never commit it), set:
   ```env
   JUDGE0_URL=https://judge0-ce.p.rapidapi.com
   JUDGE0_API_KEY=<your-rapidapi-key>
   JUDGE0_API_HOST=judge0-ce.p.rapidapi.com
   ```
4. Rebuild so the API containers pick the new env:
   ```powershell
   docker compose up -d --build
   ```
   (If the site then shows a 502, run `docker compose restart nginx` and refresh.)

## How it works

- `backend/core/views.py:execute_program` POSTs to
  `JUDGE0_URL/submissions?base64_encoded=false&wait=true` with the code,
  Judge0 language id, stdin and expected output. With `JUDGE0_API_HOST` set
  it sends the key as `X-RapidAPI-Key` plus `X-RapidAPI-Host`; without it,
  the key goes in `X-Auth-Token` for a self-hosted Judge0 server.
- Languages accepted: Python (71), JavaScript (63), Java (62), C++ (54),
  C (50), Go (60), Rust (73), plus ids 74 and 78. See `LANGUAGES` /
  `ALLOWED_LANGUAGE_IDS` in `backend/core/views.py`.
- Each problem submission runs the code once per test case and stops at the
  first failure. A problem submit costs one Judge0 call per test case, so a
  problem with 5 test cases uses 5 quota units per attempt. Lesson runs cost
  one call each. There is also a 30-second per-user throttle on submissions.

## When the limit is hit

- Judge0 answers **429** when the daily quota is used up. The API then
  returns **429 "Daily Judge0 limit reached. Try again tomorrow."** on both
  problem submits and lesson runs, and the learner sees that message. No
  submission is recorded as passed, and no points are awarded.
- A **401/403** (wrong or revoked key) returns 503 with "The code runner
  rejected the API key. Ask an administrator to check the Judge0 setup."
- To raise the limit, change the plan on RapidAPI — no code change needed.

## Tests

`backend/core/test_judge0_rapidapi.py` (mocked, no key or network needed):

```powershell
docker compose exec api python manage.py test core.test_judge0_rapidapi
```
