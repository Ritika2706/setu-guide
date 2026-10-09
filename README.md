# Setu Guide POC
Stage-aware Setu Guide assistant for the Chat with Setu Guide screen (Sambandh Setu).

## Run
    pip install -r requirements-dev.txt      # tests; runtime-only set: requirements.txt
    uvicorn app.main:app --reload --port 8000      # app.api.main:app is the same app
    pytest -q

Swagger: http://localhost:8000/docs

## Endpoint
POST /v1/guide/chat. Schema: app/schemas/guide.py (frozen by lead).
GET /health -> {"status": "ok"} (liveness for CI and deploys).
Express (requireAuth) calls this service and sends only consented fields in `context` ({"viewer": {...}, "match": {...}}).
This service never reads MongoDB.

## API Documentation
Integration-ready API document: docs/api.md (request/response schemas,
enums, safety, errors, rate limiting, caching, mock/fallback, staging checklist).
Postman collection: docs/postman/Setu-Guide.postman_collection.json
(`base_url` defaults to http://localhost:8000; set it to
https://setu-guide.onrender.com for staging).

## Day 2: Docker, config, rate limiting, caching

### Build and run (container)
    cp .env.example .env                       # optional; defaults work without it
    docker build -f docker/Dockerfile -t setu-guide-api:day2 .
    docker run --rm -p 8000:8000 --env-file .env setu-guide-api:day2
    # same thing, plus the model volume mount:
    docker compose up --build

Checks from outside the container:

    curl localhost:8000/health
    curl -X POST localhost:8000/v1/guide/chat -H "content-type: application/json" \
      -d '{"user_id":"u1","match_id":"m1","stage":"connect","intent":"next_steps"}'

The image is multi-stage (python:3.11-slim), installs with `--no-cache-dir`,
runs as a non-root user, has a HEALTHCHECK on `/health`, contains no secrets
and stays small.

**Model / knowledge-base files are not baked into the image.** Mount them at
runtime instead: `-v ./models:/app/models:ro` (docker-compose.yml already has
the line; `/app/data` works too). Once they exist, re-check `docker images` -
size must stay small, so keep mounting rather than COPYing.

### Environment variables
All configuration is read from the environment by `app/config.py`
(pydantic-settings) - nothing is hardcoded, so placeholders can change later
without code changes. `.env.example` lists every variable with dummy values;
`.env` is ignored by git and by docker.

    USE_MOCK=true                 # false calls the real orchestrator
    LLM_PROVIDER=placeholder
    LLM_API_KEY=                  # secret, required only when USE_MOCK=false
    LLM_TIMEOUT_SECONDS=10        # overall budget = this + 1s margin
    RATE_LIMIT_PER_USER=30/minute
    RATE_LIMIT_PER_IP=60/minute
    TRUSTED_PROXY=false
    CACHE_ENABLED=true
    CACHE_TTL_SECONDS=600
    CACHE_MAX_ITEMS=500
    LOG_LEVEL=INFO

Startup fails fast with one clear line when the environment cannot work
(USE_MOCK=false without LLM_API_KEY, a bad rate limit, a bad LOG_LEVEL).
The key is never logged and never appears in an error message.

### Rate limiting rules
- Per `user_id` (30/min) and per client IP (60/min) - both must allow the request.
- Exceeded -> HTTP 429 with `{"error": {"code":"rate_limited", ...}}` and a
  `Retry-After` header (seconds until the window frees up).
- `/health` is never rate limited (probes must not be throttled).
- The client IP comes from `X-Forwarded-For` **only** when `TRUSTED_PROXY=true`,
  otherwise the header is ignored (a client could not forge its own bucket).
- Counters are in memory: correct for a single instance, but **multiple
  instances need Redis** (each process would count on its own).

### Response cache rules
- Key: `stage + intent + topic + match_id + user_id` (user_id stays in the key
  until the lead confirms the final key).
- Cached only when: intent is set, there is **no** free-text `message`,
  `safety.status == "pass"`, no flags and `fallback_used == false`.
- Never cached: free-text replies, error responses (422/404/405/429/500),
  fallback replies, and anything `modified`/`blocked` or flagged.
- Every chat response carries `X-Cache: HIT` or `X-Cache: MISS`.
- `CACHE_ENABLED=false` turns caching fully off (always MISS) - use it for the
  5-run consistency check.
- Same scaling note: in-memory TTL cache, **Redis needed for multiple instances**.

### Orchestrator and LLM failure safety net
- `USE_MOCK=true` -> the Day 1 mock reply, exactly as before.
- `USE_MOCK=false` -> `app.core.orchestrator.handle_chat(request)`; it does not
  exist yet (app/core is owned by the lead), so until then real mode answers a
  safe 200 with `fallback_used: true` instead of a 500.
- The call runs under a timeout of `LLM_TIMEOUT_SECONDS + 1s`. If the
  orchestrator raises or times out: **HTTP 200**, template reply,
  `safety.status: "pass"`, `flags: []`, `fallback_used: true` - never an error,
  and the user's message is not logged.
- Structured access log, one line per request: `request_id`, `method`, `path`,
  `status`, `latency_ms`, plus `cache`, `intent`, `stage`, `fallback_used`.
  Never logs the message text, topic, `user_id`, `match_id` or the API key.
- `X-Request-Id` is echoed on every response (pass the header in to correlate).

### PLACEHOLDER values still to confirm
| Placeholder | Current value | Owner |
|---|---|---|
| `LLM_PROVIDER` | `placeholder` | responder owner |
| `LLM_TIMEOUT_SECONDS` | `10` | lead |
| `RATE_LIMIT_PER_USER` | `30/minute` | lead |
| `RATE_LIMIT_PER_IP` | `60/minute` | lead |
| `CACHE_TTL_SECONDS` | `600` | lead |
| `CACHE_MAX_ITEMS` | `500` | lead |
| `TRUSTED_PROXY` | `false` (flip behind nginx/ALB) | DevOps |
| Orchestrator entry point | `handle_chat()` missing; `handle_chat(request) -> ChatResponse` naming vs frozen `GuideRequest`/`GuideResponse` | lead |
| Model volume path | `/app/models` vs `/app/data` | AI/ML |

## Day 3: Load and failure testing

Testing only — no new features, no changes under `app/core`, `app/rag`,
`app/safety` or `app/schemas`. Full results, bug list and known limits:
[docs/load_and_failure_test_notes.md](docs/load_and_failure_test_notes.md).
How to re-run everything: [tests/README.md](tests/README.md).

- **Load tests** (`tests/load/`, Locust pinned in `requirements-dev.txt`),
  run against a container with `USE_MOCK=true` (never the real LLM quota):
  - Scenario A — mixed traffic, 70 % quick action / 30 % free text
  - Scenario B — same quick action repeated, latency split by `X-Cache` HIT/MISS
  - Scenario C — one abusive `user_id` collects 429 + `Retry-After`, other users unaffected
  - Scenario D — `/health` under load: fast and never rate limited
  - Raw run CSVs (stats, failures, `docker stats`) in `tests/load/results/`.
- **Failure tests** (`tests/failure/`, 40 tests): LLM timeout / exception /
  invalid schema → 200 template fallback (never cached), full 422
  `invalid_request` matrix, malformed JSON / wrong content-type / 1 MB body →
  clean 4xx, 404 / 405 contract, unicode & Hindi input, 500 `internal_error`
  with no stack trace, log hygiene on every path — plus container tests
  (fail-fast without a secret, restart under load → `healthy`, `docker logs`
  free of private data; these skip in CI, where the image is not built).
- Pass criteria met: 5xx rate 0 % (< 1 %), p95 57 ms on mock traffic (< 2 s),
  0 × 429 on `/health`, per-user limit isolated. Suite: **179 passing**.

## Layout
    app/api       FastAPI routes (+ chat wiring, rate limiter, cache)
    app/config.py environment settings (pydantic-settings)
    app/schemas   frozen request/response models
    app/core      orchestrator (route, context, retrieve, generate)
    app/rag       knowledge base and retrieval
    app/safety    safety guard
    data/         synthetic profiles and test conversations
    docker/       Dockerfile (multi-stage, non-root, healthcheck)
    tests/        pytest (unit + failure + load; see tests/README.md)
    docs/         API docs, evaluation report, integration notes

Each person's tasks: docs/team/<role>.md
See CONTRIBUTING.md for branch rules and owners.
