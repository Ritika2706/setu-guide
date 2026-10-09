# Setu Guide API — Integration Document

- **Service name:** Setu Guide
- **API version:** `1.0.0` (FastAPI `title="Setu Guide"`, `app/api/main.py`)
- **Source of truth:** `app/schemas/guide.py` (frozen schema), `app/api/main.py`, `app/api/chat.py`, `app/api/cache.py`, `app/api/ratelimit.py`, `app/config.py`, `app/core/orchestrator.py`, `app/safety/guard.py`
- **Interactive docs (auto-generated):** `GET /docs`, `GET /openapi.json`

## 1. Overview

Stage-aware Setu Guide assistant API for the Chat with Setu Guide screen (Sambandh Setu).
Single public chat operation: `POST /v1/guide/chat`, plus a liveness probe `GET /health`.

Current mock/staging status:

- Default runtime is **mock mode** (`USE_MOCK=true`). The mock reply body is the literal string `"(mock reply)"` with `fallback_used=false` on the normal path.
- The real orchestrator entry point `app.core.orchestrator.handle_chat` **does not exist yet** (lead-owned `app/core`). When `USE_MOCK=false`, every chat call currently returns a safe HTTP `200` with `fallback_used=true` instead of a `500` (see §17).
- Rate limiting and response caching are implemented in-process (single instance). Multi-instance deployments need Redis (see §§15–16).
- No authentication is implemented (see §3).

## 2. Base URLs

| Environment | Base URL |
|-------------|----------|
| Local | `http://localhost:8000` |
| Staging | `https://setu-guide.onrender.com` |

Run locally:

```text
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Swagger: `http://localhost:8000/docs`

## 3. Authentication

The current API does **NOT** implement any of the following:

- `Authorization` header: **not implemented**
- API key (any header/query): **not implemented**
- `X-API-Key`: **not implemented**

Do not send credentials. `401`/`403` error codes exist as static mappings but are never raised (see §14).
`internal_api_key` exists in `Settings`/`.env.example` but is documented there as "not read by this service yet".

## 4. Common Headers

Request headers:

| Header | Required | Notes |
|--------|----------|-------|
| `Content-Type: application/json` | Yes for `POST /v1/guide/chat` | JSON body parsing. |
| `X-Request-Id` | No (optional) | Caller-supplied correlation id. If absent the server generates `uuid4().hex[:12]`. |
| `X-Forwarded-For` | No | Only honored when `TRUSTED_PROXY=true`. Otherwise ignored (client IP = TCP peer). See §15. |

Response headers:

| Header | Present on | Notes |
|--------|-----------|-------|
| `X-Request-Id` | Every response (`GET /health` and all chat/error responses) | Echoes the caller value, or the generated id. Correlate with the structured access log `request_id`. |
| `X-Cache: HIT` / `X-Cache: MISS` | Successful (`200`) `POST /v1/guide/chat` only | Never present on errors (`422/404/405/429/500`) or on `/health`. `CACHE_ENABLED=false` forces `MISS`. |
| `Retry-After: <seconds>` | `429` only | Integer seconds until the limiting window frees up (minimum `1`). |

## 5. `GET /health`

- **Purpose:** Liveness probe for CI and deploy checks (`tags=["ops"]`, `app/api/main.py:133`).
- **Method/path:** `GET /health`
- **Request:** no body, no headers required. Example: `curl localhost:8000/health`
- **Response (`200`):**

```json
{"status": "ok"}
```

- **Status code:** `200` on success.
- **Headers:** `X-Request-Id` is set. No `X-Cache`, no `Retry-After`.
- **Rate-limit exemption:** `/health` is never rate limited, even when chat is already returning `429`.

## 6. `POST /v1/guide/chat` — `GuideRequest`

`POST /v1/guide/chat` with a JSON body. Success returns `200` + `GuideResponse`.

Required fields:

| Field | Type | Notes |
|-------|------|-------|
| `user_id` | `string` | Required. No `min_length`/`max_length`/`pattern` enforced. Rate-limit bucket `user:{user_id}` and part of cache key. |
| `match_id` | `string` | Required. No length/pattern enforced. Part of cache key. |
| `stage` | `Stage` enum (`string`) | Required. Exactly one of the 8 values in §7. |

Optional fields:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `intent` | `Intent` enum (`string`) \| absent | `null` | If present must be exactly one of the 4 values in §8. |
| `message` | `string` \| absent | `null` | Free text. `max_length=500`. `None`/`""`/whitespace-only counts as absent for the cross-field rule. Non-blank `message` makes the request non-cacheable. |
| `topic` | `string` \| absent | `null` | Short topic label. `max_length=100`. Part of cache key. Never logged. |
| `context` | `{"viewer": {…}, "match": {…}}` \| absent | `null` | Type `Optional[Dict[str, Dict[str, Any]]]`. Only allowlisted keys reach the orchestrator (see §11). Unknown nested keys are silently dropped and never appear in error `details`. |

Extra top-level JSON fields are silently ignored (no `extra="forbid"` on the model).

## 7. Stage enum

Exactly these 8 case-sensitive values (`app/schemas/guide.py:6`):

```text
connect
understand
reflect
discuss
agree
family
reflect_again
decision
```

Any other value → `422 invalid_request`.

## 8. Intent enum

Exactly these 4 case-sensitive values (`app/schemas/guide.py:17`):

```text
conversation_ideas
help_me_understand
next_steps
privacy_safety
```

Any other value → `422 invalid_request`. When the request omits `intent`, the response still contains a routed intent (keyword match on `message`, else `conversation_ideas`).

## 9. Cross-field validation

**`intent` OR non-blank `message` is required** (`need_intent_or_message`, `app/schemas/guide.py:48`).

- `{"stage":"connect","intent":"next_steps"}` → valid.
- `{"stage":"understand","message":"What are some good questions to ask?"}` → valid (response carries a routed `intent`).
- `{"stage":"connect"}` → `422`.
- `{"stage":"connect","intent":null,"message":"   "}` → `422` (whitespace-only does not satisfy the rule).
- `{"stage":"connect","intent":"next_steps","message":""}` → valid (intent satisfies the rule; empty message is treated as a quick action for caching).

## 10. Message/topic limits

- `message`: maximum **500 characters**. `501+` → `422`; exactly `500` → accepted (covered by tests).
- `topic`: maximum **100 characters**. `101+` → `422`; exactly `100` → accepted.

No minimum lengths are enforced on any string field.

## 11. Context allowlist

Only these 8 consented fields ever reach retrieval or the LLM (`ALLOWED_FIELDS`, `app/core/orchestrator.py:35`):

```text
interests
lifestyle
relationship_priorities
partner_type
relocation
career_importance
languages
location
```

Filtering (`_allowed`) is applied separately to `context.viewer` and `context.match`. Anything else — e.g. private reflections, readiness answers/checklist, phone numbers, contact details — is dropped in `build_context()` before retrieval/generation.

The Express layer (`requireAuth` caller) must send **only consented fields** in `context` (`{"viewer": {...}, "match": {...}}`). This service never reads MongoDB.

## 12. GuideResponse

All seven fields are always present on a `200` (`app/schemas/guide.py:60`):

| Field | Type | Limits |
|-------|------|--------|
| `intent` | `Intent` enum (`string`) | Always set (echoed or routed; fallback path uses `req.intent or conversation_ideas`). |
| `reply` | `string` | No `max_length`. Mock: `"(mock reply)"`. Safety refusal: fixed template. Real-mode failure: `FALLBACK_REPLY` (see §17). |
| `questions` | `string[]` | Default `[]`, max **5 items**. Orchestrator truncates `questions[:5]`. |
| `chips` | `string[]` | Default `[]`, max **4 items**. Orchestrator truncates `chips[:4]`. |
| `sources` | `string[]` | Default `[]`, unbounded. Currently `[]` (`retrieve` stub returns no chunks). |
| `safety` | `{"status": "pass"\|"modified"\|"blocked", "flags": SafetyFlag[]}` | Default `{"status":"pass","flags":[]}`. See §13. |
| `fallback_used` | `boolean` | Default `false`. `true` = safety block, output-safety rewrite, or real-mode exception/timeout/missing entry. Fallback replies are never cached. |

## 13. Safety

`status` values (wire strings; Python member names are `passed/modified/blocked`):

| `status` | Meaning | Consumer action |
|----------|---------|-----------------|
| `pass` | Clean reply, no flags. | Render normally. If `fallback_used=true` alongside `pass`, the backend is degraded (real-mode failure served a generic template) — safe to retry later. |
| `modified` | Output failed safety; a safe template for the intent was substituted, `flags` non-empty. | Render the returned `reply` verbatim. Optionally offer quick actions. Do not retry identically and do not show the original text (it is not returned). |
| `blocked` | Input matched a safety rule; a refusal/support template was returned, `fallback_used=true`. | Render the returned `reply` verbatim. For `distress`, surface help resources. Do not retry the same message; suggest rephrasing or quick actions. |

Six safety flags (`app/schemas/guide.py:30`):

```text
outcome_prediction
decision_request
private_data_request
prompt_injection
unsupported_claim
distress
```

Input patterns live in `app/safety/guard.py` (regexes for injection, distress/self-harm, private-data requests, outcome predictions such as "will we get married", decision requests such as "should I say yes"). Refusal priority: `distress` > `prompt_injection` > `private_data_request` > `decision_request` > `outcome_prediction` > `unsupported_claim`. Output screening blocks relationship promises ("perfect match", "guaranteed", …) and 10-digit phone/email patterns.

Blocked/modified/fallback replies are **never cached** server-side.

## 14. Error contract

Uniform shape for every failure (`app/api/main.py:61`):

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": []
  }
}
```

`details` is a string array, non-empty only for `422` (`"<field>: <pydantic-type>"` per problem, caller values never echoed; unknown nested keys collapse to the bare type). All other errors return `details: []` with fixed messages that never include caller text (`exc.detail` is deliberately ignored).

| Status | `code` | When | Notes |
|--------|--------|------|-------|
| 404 | `not_found` | Unknown route. | Fixed message `"Route not found."` |
| 405 | `method_not_allowed` | Wrong method (e.g. `GET /v1/guide/chat`). | Fixed message `"Method not allowed for this route."` |
| 422 | `invalid_request` | Request failed schema/cross-field validation. | Message `"Request did not match the schema."` + per-field `details`. Does not consume rate-limit quota. |
| 429 | `rate_limited` | Per-user or per-IP bucket exhausted. | Message `"Too many requests. Please retry shortly."` + `Retry-After` header. |
| 500 | `internal_error` | Unhandled exception. | Message `"An unexpected error occurred."` Only the exception type + traceback frames are logged; `str(exc)` is never returned. |

Currently mapped but **not actually raised** by the implementation: `400 invalid_request`, `401 unauthorized`, `403 forbidden`, `503 service_unavailable`. They exist in `_HTTP_ERRORS` for future use; do not code integrations against them today.

## 15. Rate limiting

- **Defaults:** `30 requests/minute` per `user_id` (`RATE_LIMIT_PER_USER`), `60 requests/minute` per client IP (`RATE_LIMIT_PER_IP`).
- **Both limits apply:** a request is served only if both buckets allow it; consumption is atomic (a rejected request burns neither quota).
- **Format:** `<count>/<period>`, period ∈ `second(s)/s, minute(s)/min/m, hour(s)/hr, day(s)/d`; bare `"10"` means per minute. Invalid specs fail startup with `SettingsError`.
- **`429` behavior:** `{"error":{"code":"rate_limited","message":"Too many requests. Please retry shortly.","details":[]}}` plus `Retry-After: <seconds>` (`ceil` to window expiry, minimum `1`). Log line records only the scope (`rate_limited scope=user|ip`), never the id.
- **`/health` exemption:** never rate limited.
- **`422` does not consume quota:** FastAPI validation runs before the limiter.
- **IP resolution:** `X-Forwarded-For` first entry is trusted **only** when `TRUSTED_PROXY=true` (set behind nginx/ALB you control). Default `false` uses the TCP peer, so a client cannot forge its own bucket.
- **Implementation:** in-memory sliding-window, single process. Two containers count independently — multi-instance deployments need Redis.

Manual 429 verification (do not run against production with default limits): temporarily set `RATE_LIMIT_PER_USER=3/minute`, send 4 identical quick actions, expect 3× `200` then `429` with numeric `Retry-After`.

## 16. Caching

- Every chat `200` carries `X-Cache: HIT` or `X-Cache: MISS`. Errors and `/health` never carry it.
- **Cacheable:** only clean deterministic quick-action responses — `intent` set AND no non-blank `message` AND `safety.status == "pass"` AND `flags == []` AND `fallback_used == false`.
- **Not cached:** free-text requests, `blocked`/`modified`/flagged replies, fallback replies, error responses (`422/404/405/429/500`).
- **Key:** `(stage, intent, topic, match_id, user_id)` — `user_id` stays in the key until the lead confirms the final key. Different user/topic ⇒ different entry.
- **Controls:** `CACHE_ENABLED` (default `true`; `false` forces `MISS` — use for the 5-run consistency check), `CACHE_TTL_SECONDS=600`, `CACHE_MAX_ITEMS=500`.
- **Implementation:** in-process `TTLCache`, single instance. Multi-instance deployments need Redis.

## 17. Mock / fallback behavior

- `USE_MOCK=true` (current staging default): the Day-1 mock pipeline `orchestrator.handle(req)` runs directly. Normal quick-action/message reply is `"(mock reply)"` with `fallback_used=false`. Input-safety hits still return safety-blocked `200`s with `fallback_used=true`.
- `USE_MOCK=false` (real mode): requires `LLM_API_KEY`, else startup fails fast. The call budget is `LLM_TIMEOUT_SECONDS + 1s` (`10 + 1` by default) on a worker pool. Because `app.core.orchestrator.handle_chat` is **not implemented yet**, real mode currently answers every request with HTTP `200`, the fixed template:

```text
I'm having trouble answering that right now. Please try again in a moment, or pick one of the quick actions. I'm here to help with your journey whenever you're ready.
```

with `intent = <request intent or conversation_ideas>`, `safety = {"status":"pass","flags":[]}`, `fallback_used=true`, `X-Cache: MISS` (not cached). The same `200`-fallback covers orchestrator exceptions and timeouts (only the exception type is logged; the message is not). `HTTPException` control flow (e.g. `429`) is re-raised, not converted to fallback.

The real LLM responder is **not** currently implemented — do not document or depend on real-model output.

## 18. Logging / privacy

One structured line per request: `http_request {json}` on logger `setu.guide`.

Logged fields:

```text
request_id   (== response X-Request-Id)
method
path
status
latency_ms
cache        (chat only: HIT/MISS)
intent       (chat only: response intent value)
stage        (chat only: request stage value)
fallback_used (chat only: boolean)
```

Additionally: `rate_limited scope=user|ip retry_after=…` and `orchestrator_failed mode=real type=<ExcName> fallback_used=true`, and `unhandled <ExcName>` + traceback frames for `500`s.

Explicitly **NOT** logged (asserted by tests with sentinel strings):

```text
message
topic
user_id
match_id
context (any nested PII)
API keys (LLM_API_KEY, INTERNAL_API_KEY)
request body / query string
```

Error `details` contain only schema field names + Pydantic error-type codes, never caller values.

## 19. Complete request examples

Quick-action request:

```json
{
  "user_id": "devops-day3-user-001",
  "match_id": "devops-day3-match-001",
  "stage": "connect",
  "intent": "next_steps"
}
```

```bash
curl -X POST http://localhost:8000/v1/guide/chat \
  -H "content-type: application/json" \
  -d '{"user_id":"devops-day3-user-001","match_id":"devops-day3-match-001","stage":"connect","intent":"next_steps"}'
```

Message-based request (no intent):

```json
{
  "user_id": "devops-day3-user-001",
  "match_id": "devops-day3-match-001",
  "stage": "understand",
  "message": "What are some good questions to ask?"
}
```

Request with topic/context (consented fields only):

```json
{
  "user_id": "devops-day3-user-001",
  "match_id": "devops-day3-match-001",
  "stage": "connect",
  "intent": "next_steps",
  "topic": "weekend plans",
  "context": {
    "viewer": {"interests": ["travel"], "languages": ["en"]},
    "match": {"lifestyle": "balanced"}
  }
}
```

## 20. Complete response examples

Normal successful response (`200`, `X-Cache: MISS` first time, `fallback_used=false`):

```json
{
  "intent": "next_steps",
  "reply": "(mock reply)",
  "questions": [],
  "chips": [],
  "sources": [],
  "safety": {"status": "pass", "flags": []},
  "fallback_used": false
}
```

Safety-blocked response (`200`, never cached):

```json
{
  "intent": "conversation_ideas",
  "reply": "I can't predict how a relationship will go. That depends on both of you. I can suggest questions about future plans and expectations if that helps.",
  "questions": [],
  "chips": [],
  "sources": [],
  "safety": {"status": "blocked", "flags": ["outcome_prediction"]},
  "fallback_used": true
}
```

Fallback response — real-mode failure or missing `handle_chat` (`200`, `X-Cache: MISS`, never cached):

```json
{
  "intent": "next_steps",
  "reply": "I'm having trouble answering that right now. Please try again in a moment, or pick one of the quick actions. I'm here to help with your journey whenever you're ready.",
  "questions": [],
  "chips": [],
  "sources": [],
  "safety": {"status": "pass", "flags": []},
  "fallback_used": true
}
```

Validation error (`422`):

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Request did not match the schema.",
    "details": ["stage: enum"]
  }
}
```

`details` entries are `<field>: <pydantic-type>`; exact type strings vary by failure. Caller values never appear.

Rate-limit error (`429`, header `Retry-After: 42`):

```json
{
  "error": {
    "code": "rate_limited",
    "message": "Too many requests. Please retry shortly.",
    "details": []
  }
}
```

Unknown route (`404`) and wrong method (`405`) share the envelope with codes `not_found` / `method_not_allowed` and `details: []`.

## 21. Integration guidance

- `safety.status`: `pass` → render; `modified`/`blocked` → render the returned `reply` verbatim (it is already the safe text), offer quick actions, do not retry the identical message. Route `distress` to help resources.
- `fallback_used`: `false` = full answer; `true` = degraded/templated answer (safety refusal or backend failure). `true` + `pass` + empty flags specifically means "infrastructure fallback, retryable later".
- `X-Cache`: `HIT` = byte-identical repeat of a prior clean quick action (orchestrator not re-run); `MISS` = freshly produced. Absent on errors. Do not use it as correctness signal for free-text flows (always `MISS`).
- `X-Request-Id`: send a caller-generated id per request; the same value returns in the response and appears as `request_id` in server logs for support correlation. Always generate a fresh `user_id`/`match_id` pair per test run; never send real user data.
- `context`: send only consented allowlisted fields (§11); anything else is dropped silently.
- Retries: safe to retry `429` after `Retry-After`, `500`s, and `fallback_used=true` + `pass` fallbacks. Do not blind-retry `blocked` inputs or `422`s without changing the payload.

## 22. Staging verification checklist

Base: `https://setu-guide.onrender.com` (Postman `base_url` variable; local default `http://localhost:8000`).

- [ ] `GET /health` → `200 {"status":"ok"}`, `X-Request-Id` present, no `X-Cache`.
- [ ] `POST /v1/guide/chat` quick action (`connect`/`next_steps`, synthetic ids) → `200`, 7-key body, `safety.status=="pass"`, `fallback_used==false`, `X-Cache: MISS` then `HIT` on repeat.
- [ ] Message-only request → `200` with routed `intent`.
- [ ] Invalid request (unknown `stage`) → `422 invalid_request` envelope, caller text absent from body.
- [ ] Unknown route → `404 not_found` envelope; `GET /v1/guide/chat` → `405 method_not_allowed`.
- [ ] Safety: `"Will we get married?"` → `200 blocked/outcome_prediction/fallback_used=true`; distress message → supportive reply starting `"It sounds like"`.
- [ ] Log privacy: server access line contains `request_id/method/path/status/latency_ms/cache/intent/stage/fallback_used` only; grep for the synthetic `message`/`topic`/ids returns nothing.
- [ ] Request-id correlation: send `X-Request-Id: staging-<uuid>`, assert identical response header value.
- [ ] Manual rate-limit check only (temporarily lowered env): `429` envelope + numeric `Retry-After`; `/health` still `200` during the limit.
- [ ] Confirm no secrets in responses/logs; confirm `USE_MOCK` mode and placeholder values with the lead before sign-off.
