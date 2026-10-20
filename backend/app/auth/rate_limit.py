"""Tiny in-memory sliding-window rate limiter for unauthenticated auth endpoints.

Per-process only (fine for a single uvicorn worker / dev). Call ``auth_rate_limiter.reset()``
in tests.
"""

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.exceptions import AppError

logger = logging.getLogger(__name__)


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    default_message = "Too many attempts. Please wait a minute and try again."


class RateLimiter:
    """Allow at most ``limit`` hits per ``window_seconds`` for each key."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.enabled = True
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> None:
        """Record a hit for ``key``; raise RateLimitedError when over the limit."""
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                logger.warning("Rate limit exceeded for %s", key)
                raise RateLimitedError()
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


auth_rate_limiter = RateLimiter(limit=10, window_seconds=60.0)
#: Per-account login limit, so one account can't be brute-forced from many IPs.
login_account_limiter = RateLimiter(limit=10, window_seconds=15 * 60.0)


def rate_limit_auth(request: Request) -> None:
    """FastAPI dependency: 10 requests/minute per client IP per auth endpoint."""
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.hit(f"{request.url.path}:{client_ip}")


def rate_limit_login_account(email: str) -> None:
    """10 login attempts per 15 minutes per account (email), whatever the client IP."""
    login_account_limiter.hit(f"login:{email.strip().lower()}")
