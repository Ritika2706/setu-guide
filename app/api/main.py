"""FastAPI app: routes and error handlers. Owner: DevOps 1 (app/api/).

Error contract (identical shape for every failure):
    {"error": {"code": "...", "message": "...", "details": []}}
Rule: caller input is never echoed back into an error message or a log line,
so details are built from schema field names and Pydantic error type codes only.
"""
import logging
import traceback
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.orchestrator import handle
from app.schemas.guide import GuideRequest, GuideResponse

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("setu.guide")

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


@app.get("/health", tags=["ops"])
def health() -> Dict[str, str]:
    """Liveness probe for CI and deploy checks."""
    return {"status": "ok"}


@app.post("/v1/guide/chat", response_model=GuideResponse, tags=["guide"])
def chat(req: GuideRequest) -> GuideResponse:
    return handle(req)


# Day 2 notes: rate limiting raises HTTPException(status_code=429) and the
# handler above already returns the rate_limited format. If the LLM fails or
# times out later, answer 200 with fallback_used: true instead of an error.
