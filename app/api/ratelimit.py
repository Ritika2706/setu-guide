"""In-memory sliding-window rate limiter (per user_id and per client IP).

Single process only - two containers would each get their own counters, so a
multi-instance deployment needs Redis (see README, "Scaling note").
Owner: DevOps 1.
"""
import math
import threading
import time
from typing import Dict, List, Tuple

from fastapi import Request

Key = Tuple[str, int, int]  # (bucket key, allowed count, window seconds)

_MAX_KEYS = 10_000
_MAX_WINDOW = 86_400  # longest period the config supports (day)


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: Dict[str, List[float]] = {}

    def hit(self, keys: List[Key]) -> Tuple[bool, str, int]:
        """Consume one request from every bucket.

        Returns (allowed, blocked_key, retry_after_seconds). Buckets are only
        consumed when all of them allow the request, so a rejected IP does not
        burn the user's quota.
        """
        now = time.monotonic()
        with self._lock:
            for key, limit, window in keys:
                hits = self._hits.setdefault(key, [])
                cutoff = now - window
                expired = 0
                while expired < len(hits) and hits[expired] <= cutoff:
                    expired += 1
                if expired:
                    del hits[:expired]
                if len(hits) >= limit:
                    retry_after = max(1, int(math.ceil(hits[0] + window - now)))
                    return False, key, retry_after
            for key, _, _ in keys:
                self._hits[key].append(now)
            self._sweep(now)
            return True, "", 0

    def _sweep(self, now: float) -> None:
        """Keep the dict bounded: drop buckets older than the longest window."""
        if len(self._hits) <= _MAX_KEYS:
            return
        cutoff = now - _MAX_WINDOW
        for key in [k for k, v in self._hits.items() if not v or v[-1] < cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        """Test helper - clears every counter."""
        with self._lock:
            self._hits.clear()


def client_ip(request: Request, trusted_proxy: bool) -> str:
    """X-Forwarded-For is trusted only when TRUSTED_PROXY=true, otherwise a
    client could forge its own rate-limit bucket by sending the header."""
    if trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


limiter = RateLimiter()
