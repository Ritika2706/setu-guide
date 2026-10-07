"""In-memory TTL cache for identical quick-action responses.

Only cacheable when the request is a pure quick action (intent set, no free
text) and the reply is a normal one: safety "pass", no flags, no fallback.
Errors, free-text replies and anything modified or blocked never enter the
cache. Single process only - see README for the Redis note.
Owner: DevOps 1.
"""
import threading
from typing import Any, Optional, Tuple

from cachetools import TTLCache

from app.config import Settings
from app.schemas.guide import GuideRequest, GuideResponse, SafetyStatus

CacheKey = Tuple[str, str, str, str, str]


def cache_key(req: GuideRequest) -> CacheKey:
    """stage + intent + topic + match_id + user_id.

    user_id is included to stay safe until the lead confirms the final key.
    """
    return (
        req.stage.value,
        req.intent.value if req.intent else "",
        req.topic or "",
        req.match_id,
        req.user_id,
    )


def is_cacheable(req: GuideRequest, resp: GuideResponse) -> bool:
    if req.intent is None:
        return False
    if req.message and req.message.strip():
        return False
    if resp.fallback_used:
        return False
    if resp.safety.status != SafetyStatus.passed:
        return False
    return not resp.safety.flags


class ResponseCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: Optional[TTLCache] = None
        self._spec: Optional[Tuple[int, int]] = None

    def _store(self, settings: Settings) -> TTLCache:
        spec = (settings.cache_max_items, settings.cache_ttl_seconds)
        if self._cache is None or self._spec != spec:
            # Rebuilt when the limits change, so tests can flip the config.
            self._cache = TTLCache(maxsize=spec[0], ttl=spec[1])
            self._spec = spec
        return self._cache

    def get(self, key: CacheKey, settings: Settings) -> Any:
        with self._lock:
            return self._store(settings).get(key)

    def put(self, key: CacheKey, value: Any, settings: Settings) -> None:
        if settings.cache_ttl_seconds <= 0:
            return
        with self._lock:
            self._store(settings)[key] = value

    def clear(self) -> None:
        with self._lock:
            self._cache = None
            self._spec = None


response_cache = ResponseCache()
