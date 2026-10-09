# Load and failure test notes - Setu Guide API (Day 3)

Owner: DevOps 1. Testing only - no new features. How to re-run everything:
[`tests/README.md`](../tests/README.md).

## 1. Environment

| Item | Value |
|---|---|
| URL tested | `http://localhost:8000` (placeholder - staging URL to be confirmed) |
| Service code | commit `4753b75` (Day 2 merge, PR #4). Day 3 changes are tests/docs only. |
| Image | `setu-guide-api:day3`, built from `docker/Dockerfile` (python:3.11-slim, non-root) |
| `USE_MOCK` | `true` for every load scenario (no real LLM is contacted - free-tier quota) |
| Real-mode run | one small run with `USE_MOCK=false` + placeholder key: it goes through the LLM safety net (`handle_chat` does not exist yet) and answers 200 with `fallback_used=true` |
| Container resources | no CPU/memory limit set; Docker Desktop VM (7.6 GiB). Usage measured with `docker stats` per run |
| Rate limits during load runs | raised to `100000/minute` per user and per IP **for the run only**, except Scenario D (defaults) and Scenario C (user limit left at 30/minute) |
| Locust | `locust==2.46.7` (pinned in `requirements-dev.txt`) |
| Date | 2026-10-08 |

## 2. Load test results

Pass criteria (from the brief): error rate (5xx) < 1 %; p95 < 2 s for cached or
mock replies, < 12 s with the real LLM. Raw locust output for every run is in
`tests/load/results/` (`*_stats.csv`, `*_failures.csv`, `*_docker_stats.csv`;
the `*_failures.csv` files are empty except Scenario C, where it lists only
the deliberate 429s, and no run produced a single locust exception).

### Scenario D - /health under load (container with DEFAULT limits)

Profile: 20 users, 60 s, ramp 30 s, `USE_MOCK=true`, default rate limits
(30/min per user, 60/min per IP).

| Metric | Value |
|---|---|
| Requests | 3397 |
| Requests/s | 57.3 |
| p50 / p95 / p99 | 8 ms / 17 ms / 23 ms (max 34 ms) |
| Errors by status | none - 0 x 4xx, 0 x 5xx (0.00 %) |
| 429s | **0** - `/health` is not rate limited even though 57 req/s from one IP is far above the 60/min IP limit |
| Cache hit ratio | n/a - `/health` is not a chat request |
| Container CPU | min 0.4 %, avg 17.2 %, max 28.9 % (10 samples / 60 s) |
| Container memory | 38.8 - 38.9 MiB (0.5 % of the VM) |

Result: **PASS**.

### Scenario A - mixed traffic (70 % quick action / 30 % free text)

Profile: 20 users, 5 minutes, ramp 30 s, `USE_MOCK=true`, rate limits raised
for the run. `TARGET_URL` placeholder.

| Metric | Value |
|---|---|
| Requests | 5428 total: 3834 quick-action (70.6 %) + 1594 free text (29.4 %) |
| Requests/s | 18.1 |
| p50 / p95 / p99 (max) | 50 ms / 57 ms / 66 ms (max 110 ms) |
| Errors by status | none - 0 x 4xx, 0 x 5xx (0.00 %) |
| 429s | 0 (limits raised for this run only, as planned) |
| Cache hit ratio (access log) | 49.8 % overall (2706 HIT / 5436 chat requests); **70.5 % of quick actions** - free text is deliberately never cached, which is what drags the overall number down |
| Container CPU | avg 9.2 %, max 37.3 % (48 samples / 5 min) |
| Container memory | 38.8 -> 41.6 MiB |

Result: **PASS** - p95 57 ms against the 2 s criterion, error rate 0 % against < 1 %.

### Scenario B - cache effect (same quick action repeated)

Profile: 20 users, 60 s, `USE_MOCK=true`, rate limits raised. Each virtual
user repeats 3 fixed quick actions, so request 1 per key is a MISS and every
repeat is a HIT; locust splits them (`B:MISS` / `B:HIT`).

| Metric | B:MISS | B:HIT |
|---|---|---|
| Requests | 59 | 4455 |
| p50 / p95 / p99 (max) | 49 ms / 64 ms / 72 ms (max 72 ms) | 51 ms / 61 ms / 71 ms (max 150 ms) |
| Errors | 0 | 0 |

Cache hit ratio (access log): **98.7 %** (4476 HIT / 4535 chat requests).
Container CPU / memory: avg 29.6 %, max 36.1 %; 41.2 -> 42.1 MiB.

Result: **PASS** - both variants are far below the 2 s p95 criterion and
error-free. The MISS/HIT latency gap is small today because the mock reply
itself only costs ~50 ms (and MISS has just 59 samples, all from the first
cycle); what this scenario proves quantitatively is the 98.7 % hit ratio -
98.7 % of requests never reach the orchestrator. Once the real LLM is wired
in, MISS will cost seconds while HIT stays in these milliseconds.

### Scenario C - rate limit behaviour (one abusive user_id)

Profile: 6 locust users (3 instances sharing the single id
`load_abusive_user` at ~5 req/s, plus 3 innocent users at 3-6 s intervals),
90 s, `USE_MOCK=true`, container with `RATE_LIMIT_PER_USER=30/minute`
(default) and `RATE_LIMIT_PER_IP=100000/minute`.

| Metric | Value |
|---|---|
| Requests (abusive id) | 1302: 60 x 200 + 1242 x 429 (95.4 % of its requests blocked) |
| 429 responses for the abusive id | 1242 - each carries `Retry-After: 60` and the standard body `{"error": {"code": "rate_limited", "message": "Too many requests. Please retry shortly.", "details": []}}` (both verified with a direct request after the run) |
| 429 responses for the innocent users | **0** - 58 requests, all 200 |
| p95 (abusive, 200s) | 57 ms |
| p95 (innocent users) | 55 ms (p50 48 ms) |
| Errors other than 429 | 0 |
| Container CPU / memory | avg 8.2 %, max 32.5 %; 39.0 -> 39.8 MiB |

Result: **PASS** - the limit is per `user_id`: the one id above 30/minute
collects 429s while the other users are untouched.

### Small real-mode run (the one allowed run towards the "real" path)

Profile: 5 users, 60 s, Scenario A traffic, `USE_MOCK=false` with a
placeholder key. No provider is contacted (`handle_chat` is not implemented
yet), so this exercises the LLM safety net under light load, not a provider.

| Metric | Value |
|---|---|
| Requests / requests per second | 275 (196 quick action + 79 free text) / 4.7 |
| p50 / p95 / p99 (max) | 50 ms / 56 ms / 66 ms (max 306 ms) - well under the 12 s criterion |
| 5xx errors | 0 (and 0 x 429) |
| Responses with `fallback_used=true` | 100 % (276 of 276 chat requests in the access log) - no provider is contacted because `handle_chat` does not exist yet |
| Cache hit ratio | 0 % (276 MISS / 0 HIT) - fallback replies are never cached, as designed |
| Container CPU / memory | avg 2.6 %, max 3.4 %; 38.9 MiB |

Result: **PASS** for the safety-net path. Re-run this scenario with the real
LLM once `handle_chat` exists (then check p95 < 12 s).

## 3. Failure test results

Suite: `tests/failure/` (pytest, `python -m pytest tests/failure -q` ->
40 tests: 37 in-process + 3 container tests). All ran on 2026-10-08.

| Test | Input | Expected | Actual | Pass/Fail |
|---|---|---|---|---|
| LLM timeout | orchestrator sleeps longer than `LLM_TIMEOUT_SECONDS` | 200, template reply, `fallback_used=true`, `safety.status="pass"`, `flags=[]`, not cached | as expected (timeout enforced in < 0.9 s, both requests `X-Cache: MISS`) | PASS |
| LLM exception | orchestrator raises `RuntimeError` with text | same as above, exception text not in the response | as expected, no leak | PASS |
| LLM invalid schema | `{"intent": "not-a-real-intent", "reply": 12345}` | fallback reply, no 500 | as expected | PASS |
| LLM invalid JSON | truncated JSON string from the orchestrator | fallback reply, no 500 | as expected | PASS |
| LLM wrong type | orchestrator returns `42` | fallback reply, no 500 | as expected | PASS |
| `handle_chat` missing | real mode, entry point not implemented yet | 200 fallback, never 500 | as expected | PASS |
| Fallback not cached | 2 identical quick actions while the LLM is down | both `X-Cache: MISS` | as expected | PASS |
| Recovery | LLM works again after a failure | next reply served normally, `fallback_used=false` | as expected | PASS |
| Unexpected internal exception | handler raises | 500 `internal_error`, `details: []`, no stack trace / file names / exception text | as expected | PASS |
| Unknown stage / intent | `"stage": "teleport"`, `"intent": "make_me_rich"` | 422 `invalid_request`, `stage: enum` / `intent: enum` | as expected | PASS |
| Missing `user_id` / `match_id` | field removed | 422 `invalid_request`, `field: missing` | as expected | PASS |
| Neither intent nor message | both absent | 422 `invalid_request`, `value_error` | as expected | PASS |
| Message > 500 chars | 1050-char message with canary text | 422, `message: string_too_long`, canary not echoed | as expected | PASS |
| Topic > 100 chars | 306-char topic with canary text | 422, `topic: string_too_long`, canary not echoed | as expected | PASS |
| Wrong types | numbers for `user_id`/`match_id`/`stage`, list for `intent`, `null` values | 422 `invalid_request` with `string_type`/`enum` details | as expected | PASS |
| Empty body / empty JSON `{}` | `content=b""` / `{}` | 422 `invalid_request` (missing fields listed) | as expected | PASS |
| Malformed JSON | `{"user_id": ` + canary | 422 `invalid_request`, canary not echoed | as expected (`json_invalid`) | PASS |
| Wrong `Content-Type` | `text/plain` with a JSON body, and form-encoded data | clean 4xx in the standard format | 422 `invalid_request` | PASS |
| Very large body | ~1 MB message | clean 4xx, no 413/500 | 422 `invalid_request`, payload not echoed | PASS |
| Unknown route | `GET /nope/such/path`, `POST /v1/guide/unknown` | 404 `not_found` in standard format | as expected | PASS |
| Wrong method | `GET`/`DELETE /v1/guide/chat` | 405 `method_not_allowed` | as expected | PASS |
| Unicode / emoji / Hindi / RTL / zero-width | 6 payloads incl. Hindi, emoji, Arabic, combining accents | 200, no crash | as expected | PASS |
| Log hygiene (all paths) | one test drives 200 + 422 + 404 + 429 + 500 with marker message/topic/ids/API key | no marker in any log line; 429 log only names the scope | as expected, all 5 statuses logged, no marker | PASS |
| Response hygiene | 200 and 422 bodies | no API key / caller ids in responses | as expected | PASS |
| Container: missing secret | `docker run -e USE_MOCK=false -e LLM_API_KEY=` | exits non-zero with `LLM_API_KEY is required when USE_MOCK=false` | as expected | PASS |
| Container: restart under load | 5 threads x ~10 req/s while `docker restart` | HTTP returns, `HEALTHCHECK` turns `healthy`, no 5xx/429 while reachable | back in < 90 s, `healthy`, 0 errors, > 100 successful chat + health requests in the window | PASS |
| Container: log hygiene | marker message/topic/ids + API key in the container env | `docker logs` contains the structured lines but no marker | as expected | PASS |
| Load-run log hygiene | grep of the container log after the load runs for `load_user_`, `load_match_`, free-text prompt fragments and the placeholder API key | no match | 0 matches across 1700 log lines (only the structured access-log fields) | PASS |

## 4. Bugs found

| # | Where | Description | Severity | Fixed? | Owner |
|---|---|---|---|---|---|
| - | - | **No bug found in the API layer (app/api, config, Docker).** All 40 Day 3 failure tests and the load scenarios behaved exactly as specified: clean 4xx in the standard error contract, safe 200 fallback for every LLM failure mode, no 5xx except the deliberate internal-error test, no private data in logs, health endpoint never rate limited, container fails fast and recovers after restart. | - | - | - |

(If a later run against staging finds something, it goes in this table: fixed
issues stay here with the PR, orchestrator/RAG/safety issues are written up
for their owner with steps to reproduce and are NOT fixed by DevOps 1.)

## 5. Known limits

- **Single instance only.** The rate limiter and the response cache are
  in-memory and per-process: two containers would each keep their own counters
  and cache, so a multi-instance deployment needs Redis (or equivalent).
  Verified single-container here.
- **Free-tier LLM quota.** All load runs use `USE_MOCK=true`; only one small
  run (5 users / 60 s) used the real-mode path, and even that contacts no
  provider because `handle_chat` does not exist yet. Once a real provider is
  wired in, re-run Scenario A with the mock off and check the < 12 s p95
  criterion.
- **Rate limiting runs after body validation**, so rejected (422) requests do
  not consume quota - deliberate, but worth knowing when reading the numbers.
- **In-process timeout thread.** On an orchestrator timeout the worker thread
  runs until its own sleep/IO ends (bounded by the orchestrator itself); the
  pool has 8 threads. Fine for a POC, worth revisiting for production.
- **Container tests need Docker** and a locally built image; CI skips them
  (the image is not built there). They ran on the dev machine for these notes.
- **Synthetic data only.** `data/` has no evaluation scenarios yet, so load
  inputs are synthetic (8 stages x 4 intents + free text, see
  `tests/load/common.py`). Re-run with the evaluation owner's cases when they
  land.
- Locust ran on the same machine as the container (localhost), so client-side
  CPU is shared; absolute latency may differ on staging (a remote URL will
  add network time).

## 6. Recommendations for production (short)

- Put Redis behind the rate limiter and cache before scaling past one
  instance.
- Keep `/health` out of the rate limiter (already done) and keep it out of
  access-log noise if log volume grows.
- Alert on `fallback_used=true` rate and on 5xx count; both are already in
  the structured access log.
- Re-run Scenario A on staging with the real LLM once `handle_chat` exists,
  and re-check p95 < 12 s and error rate < 1 % there.

## 7. Placeholder values still unconfirmed

| Placeholder | Current value | Needs confirmation |
|---|---|---|
| `TARGET_URL` | `http://localhost:8000` | staging URL |
| Load profile | 20 users, 5 min, 30 s ramp | as given in the brief - confirm it is the final profile |
| Pass criteria | 5xx < 1 %, p95 < 2 s (mock/cached), < 12 s (real LLM) | confirm |
| `RATE_LIMIT_PER_USER` / `RATE_LIMIT_PER_IP` | `30/minute` / `60/minute` | lead (unchanged from Day 2) |
| `CACHE_TTL_SECONDS` / `CACHE_MAX_ITEMS` | `600` / `500` | lead (unchanged from Day 2) |
| `LLM_TIMEOUT_SECONDS` | `10` (+1 s margin) | lead / responder owner |
| `LLM_PROVIDER`, `handle_chat` entry point | `placeholder`, not implemented | AI/ML owner (blocks the real-LLM run) |
| Test data | synthetic stand-ins in `tests/load/common.py` | evaluation owner's scenarios in `data/` |
