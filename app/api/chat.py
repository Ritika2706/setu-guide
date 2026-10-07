"""POST /v1/guide/chat - rate limiting, response caching, orchestrator wiring.

Flow: rate limit -> cache lookup -> mock or real orchestrator (with timeout and
a safety net) -> cache store -> X-Cache header.

Owner: DevOps 1 (app/api/). The request/response schema is frozen in
app/schemas, and app/core, app/rag and app/safety belong to the lead and the
AI/ML interns - this module only calls into them.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request, Response

from app.api.cache import cache_key, is_cacheable, response_cache
from app.api.ratelimit import client_ip, limiter
from app.config import Settings, get_settings
from app.schemas.guide import GuideRequest, GuideResponse, Intent

logger = logging.getLogger("setu.guide.chat")

# Overall budget is LLM_TIMEOUT_SECONDS + this margin.
TIMEOUT_MARGIN_SECONDS = 1.0
_ORCHESTRATOR_WORKERS = 8
_POOL = ThreadPoolExecutor(max_workers=_ORCHESTRATOR_WORKERS, thread_name_prefix="orch")

# Safe template used when the orchestrator fails or times out. HTTP 200,
# safety "pass", no flags, fallback_used true - never an error status.
FALLBACK_REPLY = (
    "I'm having trouble answering that right now. Please try again in a moment, "
    "or pick one of the quick actions. I'm here to help with your journey whenever you're ready."
)


class OrchestratorUnavailable(RuntimeError):
    """USE_MOCK=false but app.core.orchestrator.handle_chat does not exist yet (TODO: lead)."""


def fallback_response(req: GuideRequest) -> GuideResponse:
    return GuideResponse(
        intent=req.intent or Intent.conversation_ideas,
        reply=FALLBACK_REPLY,
        fallback_used=True,
    )


def _enforce_rate_limits(req: GuideRequest, http_request: Request, settings: Settings) -> None:
    user_count, user_window = settings.user_limit
    ip_count, ip_window = settings.ip_limit
    allowed, blocked_key, retry_after = limiter.hit([
        (f"user:{req.user_id}", user_count, user_window),
        (f"ip:{client_ip(http_request, settings.trusted_proxy)}", ip_count, ip_window),
    ])
    if not allowed:
        # Scope only: the bucket key holds an id, so it is never logged in full.
        logger.info("rate_limited scope=%s retry_after=%s", blocked_key.split(":", 1)[0], retry_after)
        raise HTTPException(status_code=429, headers={"Retry-After": str(retry_after)})


def _call_with_timeout(entry: Callable[[GuideRequest], Any], req: GuideRequest,
                       settings: Settings) -> Any:
    future = _POOL.submit(entry, req)
    try:
        return future.result(timeout=settings.llm_timeout_seconds + TIMEOUT_MARGIN_SECONDS)
    except FutureTimeoutError:
        future.cancel()
        raise TimeoutError(f"orchestrator exceeded {settings.llm_timeout_seconds}s") from None


def _produce(req: GuideRequest, entry: Optional[Callable], settings: Settings) -> GuideResponse:
    if settings.use_mock:
        # Day 1 mock path: returned directly, so failures surface as they did on Day 1.
        return entry(req)
    try:
        if entry is None:
            raise OrchestratorUnavailable("app.core.orchestrator.handle_chat is not implemented yet")
        result = _call_with_timeout(entry, req, settings)
        if not isinstance(result, GuideResponse):
            result = GuideResponse.model_validate(result)
        return result
    except HTTPException:
        raise  # framework control flow (404/429/...) is not an LLM failure
    except Exception as exc:
        # Never log the message, topic or ids - exception type only.
        logger.warning("orchestrator_failed mode=real type=%s fallback_used=true", type(exc).__name__)
        return fallback_response(req)


def _remember(http_request: Request, req: GuideRequest, resp: GuideResponse,
              cache_state: str) -> None:
    """Fields for the structured access log - no message, topic or ids."""
    http_request.state.log_extra = {
        "cache": cache_state,
        "intent": resp.intent.value,
        "stage": req.stage.value,
        "fallback_used": resp.fallback_used,
    }


def run_chat(req: GuideRequest, http_request: Request, http_response: Response,
             entry: Optional[Callable]) -> GuideResponse:
    settings = get_settings()
    _enforce_rate_limits(req, http_request, settings)

    caching = settings.cache_enabled
    key = cache_key(req) if caching else None
    if key is not None:
        cached = response_cache.get(key, settings)
        if cached is not None:
            http_response.headers["X-Cache"] = "HIT"
            _remember(http_request, req, cached, "HIT")
            return cached

    resp = _produce(req, entry, settings)
    http_response.headers["X-Cache"] = "MISS"
    if key is not None and is_cacheable(req, resp):
        response_cache.put(key, resp, settings)
    _remember(http_request, req, resp, "MISS")
    return resp
