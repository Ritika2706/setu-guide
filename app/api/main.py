"""FastAPI app: routes and error handlers. Owner: DevOps 1 (app/api/).

Error contract (identical shape for every failure):
    {"error": {"code": "...", "message": "...", "details": []}}
Rule: caller input is never echoed back into an error message or a log line,
so details are built from schema field names and Pydantic error type codes only.
"""
import json
import logging
import time
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.chat import run_chat
from app.config import get_settings
from app.core.orchestrator import handle
from app.schemas.guide import GuideRequest, GuideResponse

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("setu.guide")

# Fail fast: an unusable environment (USE_MOCK=false without LLM_API_KEY, a bad
# rate limit, a bad LOG_LEVEL) stops the process here with one clear message
# instead of failing on the first request.
settings = get_settings()
logging.getLogger("setu.guide").setLevel(settings.log_level)

app = FastAPI(
    title="Setu Guide",
    version="1.0.0",
    description="Stage-aware Setu Guide assistant. POST /v1/guide/chat, GET /health.",
)

# Only these names may appear in error details. Anything else in an error path
# (e.g. a key the caller put inside `context`) is dropped, so no user text can
# travel back in a response or a log line.
_REQUEST_FIELDS = frozenset(
    {"user_id", "match_id", "stage", "intent", "message", "topic", "context"}
)

# status code -> (code, message). Messages are fixed strings, never built from input.
_HTTP_ERRORS: Dict[int, tuple] = {
    400: ("invalid_request", "Request could not be processed."),
    401: ("unauthorized", "Missing or invalid credentials."),
    403: ("forbidden", "Access to this resource is not allowed."),
    404: ("not_found", "Route not found."),
    405: ("method_not_allowed", "Method not allowed for this route."),
    429: ("rate_limited", "Too many requests. Please retry shortly."),
    503: ("service_unavailable", "Service temporarily unavailable."),
}


def _error(code: str, message: str, details: Optional[List[Any]] = None) -> Dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or []}}


def _validation_details(exc: RequestValidationError) -> List[str]:
    """`<schema field>: <pydantic error type>` per problem, caller values excluded."""
    details: List[str] = []
    for err in exc.errors():
        err_type = str(err.get("type") or "invalid")
        loc = err.get("loc") or ()
        field = loc[1] if len(loc) > 1 and isinstance(loc[1], str) and loc[1] in _REQUEST_FIELDS else None
        details.append(f"{field}: {err_type}" if field else err_type)
    return details


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error("invalid_request", "Request did not match the schema.",
                       _validation_details(exc)),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # exc.detail is deliberately ignored: it can carry caller text.
    code, message = _HTTP_ERRORS.get(exc.status_code, ("http_error", "Request could not be processed."))
    return JSONResponse(status_code=exc.status_code, content=_error(code, message),
                        headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def internal_error(_: Request, exc: Exception) -> JSONResponse:
    # Type name and code locations only: str(exc) may contain request data.
    frames = "".join(traceback.format_tb(getattr(exc, "__traceback__", None)))
    logger.error("unhandled %s -> 500 internal_error\n%s", type(exc).__name__, frames)
    return JSONResponse(status_code=500,
                        content=_error("internal_error", "An unexpected error occurred."))


@app.middleware("http")
async def structured_access_log(request: Request, call_next):
    """One structured line per request: request id, method, path, status,
    latency and (for chat) cache/intent/stage/fallback.
    Never logs the body, query string, message, topic, ids or the API key."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Escapes to the Exception handler below, which builds the 500 body.
        _log_http(request, request_id, 500, started)
        raise
    response.headers["X-Request-Id"] = request_id
    _log_http(request, request_id, response.status_code, started)
    return response


def _log_http(request: Request, request_id: str, status: int, started: float) -> None:
    payload: Dict[str, Any] = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    payload.update(getattr(request.state, "log_extra", None) or {})
    logger.info("http_request %s", json.dumps(payload, sort_keys=True))


@app.get("/health", tags=["ops"])
def health() -> Dict[str, str]:
    """Liveness probe for CI and deploy checks. Never rate limited."""
    return {"status": "ok"}


def _orchestrator_entry(config) -> Optional[Callable]:
    """Mock entry today; real entry once the lead adds handle_chat.

    TODO(lead): app.core.orchestrator.handle_chat(request) -> ChatResponse does
    not exist yet (app/core is owned by the lead, so nothing was added there).
    Until then real mode reports OrchestratorUnavailable, and the safety net in
    app/api/chat.py answers 200 with fallback_used=true.

    `handle` is read from this module's globals at call time on purpose, so
    tests can patch app.api.main.handle.
    """
    if config.use_mock:
        return handle
    from app.core import orchestrator
    return getattr(orchestrator, "handle_chat", None)


@app.post("/v1/guide/chat", response_model=GuideResponse, tags=["guide"])
def chat(req: GuideRequest, request: Request, response: Response) -> GuideResponse:
    return run_chat(req=req, http_request=request, http_response=response,
                    entry=_orchestrator_entry(get_settings()))
