# Coding challenges — Judge0 self-hosted (free)

Coding challenges already exist in Venus Learning: instructors create Problems
with test cases, learners submit code from `/coding-problems`, and the backend
grades each submission against the test cases (+10 points on first pass).
Lesson coding exercises (`/api/lessons/<id>/run/`) use the same runner.

The runner is Judge0, and since this change it runs **free, self-hosted, as
part of the same Docker Compose stack** — no RapidAPI account, no key, no
card, no per-submission charge. The only cost is the machine it runs on.

## What was added

`compose.yaml` gains four services, adapted from the official Judge0 CE
`docker-compose.yml` (judge0/judge0 master, fetched 2026-11-28):

| Service | Image | What it does |
| --- | --- | --- |
| `judge0-server` | `judge0/judge0:1.13.1` | The Judge0 API on internal port 2358 |
| `judge0-worker` | `judge0/judge0:1.13.1` | Runs submissions (`./scripts/workers`) |
| `judge0-db` | `postgres:16.2` | Judge0's own database (volume `judge0-data`) |
| `judge0-redis` | `redis:7.2.4` | Judge0's job queue |

- The image is pinned to `1.13.1`, the latest Judge0 CE release
  (2024-04-18); the official file uses the floating `:latest` tag.
  `postgres:16.2` and `redis:7.2.4` are taken as-is from the official file.
- Services are named `judge0-*` because the official names (`db`, `redis`)
  would collide with this project's own MySQL/Redis services. The volumes
  are separate too: Judge0's Postgres uses `judge0-data`, never the app's
  `mysql-data` / `redis-data`.
- **No ports are published.** Only the API containers reach Judge0, at
  `http://judge0-server:2358` inside the Compose network. Nothing on the
  laptop or the internet can call it directly.
- `judge0-server` and `judge0-worker` run `privileged: true`, as the
  official file requires — Judge0's `isolate` sandbox needs it.
- `deploy/judge0.conf` (mounted read-only into server/worker) points Judge0
  at `judge0-db` / `judge0-redis` and turns telemetry off. Auth is off
  (`AUTHN_TOKEN` empty, Judge0's default): the API calls it with no key,
  which is safe only because it is internal-only — do not publish port
  2358 without setting an auth token first.
- Passwords for Judge0's Postgres/Redis live in the project's `.env`
  (`JUDGE0_POSTGRES_PASSWORD`, `JUDGE0_REDIS_PASSWORD`), not in
  `judge0.conf` or git. Do not add password lines to `judge0.conf`: it is
  sourced at container start, and a blank password line would override
  the environment value.

No backend code change was needed: `execute_program` in
`backend/core/views.py` already sends a plain request when `JUDGE0_URL` is
set with no `JUDGE0_API_HOST` and no `JUDGE0_API_KEY`, and keeps the
RapidAPI headers for anyone who sets `JUDGE0_API_HOST` instead.

## First run (on the laptop)

1. Pull the merge, then update the project's `.env`:
   - If your `.env` still has the RapidAPI values from before, replace them:
     ```env
     JUDGE0_URL=http://judge0-server:2358
     JUDGE0_API_KEY=
     JUDGE0_API_HOST=
     ```
   - Add the two Judge0 passwords (any two different random strings):
     ```env
     JUDGE0_POSTGRES_PASSWORD=<a-random-password>
     JUDGE0_REDIS_PASSWORD=<a-different-random-password>
     ```
   - If you copied `.env` from `.env.example`, these lines are already
     there — just replace the `REPLACE_WITH_...` placeholders.
2. Rebuild (first pull is large — the image bundles compilers for 60+
   languages, so allow time and disk space):
   ```powershell
   docker compose up -d --build
   ```
   If the site then shows a 502, run `docker compose restart nginx`.
3. Check the services are up:
   ```powershell
   docker compose ps
   ```
   `judge0-server`, `judge0-worker`, `judge0-db` and `judge0-redis` should
   all show running/healthy.
4. Check the API can reach Judge0 (from inside the Compose network):
   ```powershell
   docker compose exec api1 python -c "import urllib.request; print(urllib.request.urlopen('http://judge0-server:2358/languages', timeout=5).status)"
   ```
   It should print `200` and a JSON list of languages.
5. Run the mocked tests (no key or network needed):
   ```powershell
   docker compose exec api1 python manage.py test core.test_judge0_rapidapi core.test_judge0_selfhosted
   ```
6. Submit one coding problem as a learner. It should grade instead of
   the old 503. Each problem submission costs one Judge0 call per test
   case; lesson runs cost one call each. There is no quota to use up.

## Known risk — read this before the first run

Self-hosted Judge0's `isolate` sandbox needs privileged containers and
cgroup v1, which Docker Desktop / WSL2 does not give by default. So the
first local run **may fail with isolate errors even if this config is
right** — typically the server/worker start, but submissions fail with an
isolate/cgroup error. If that happens, the config is not necessarily
wrong; it is the known platform limit, and it will show up in
`docker compose logs judge0-worker`.

**Fallback if self-hosting does not run on the laptop:** use a free
Judge0-compatible hosted endpoint instead (for example OnlineCompiler.io,
free up to 100,000 runs/month). That needs only a URL/key change — set
`JUDGE0_URL` to the hosted endpoint and `JUDGE0_API_KEY` to its key in
`.env`, no code change — but it is **not** built in this change.

## RapidAPI alternative (paid, still supported)

The RapidAPI wiring from before is untouched: if `JUDGE0_API_HOST` is set,
the backend sends `X-RapidAPI-Key` / `X-RapidAPI-Host` as before — see
`docs/judge0-rapidapi.md`. RapidAPI Basic is $0.0017 per submission from
the first run and Pro is $44.99/month for 2,000/day, so self-hosted is
the free default and RapidAPI is only for anyone who prefers hosted.
