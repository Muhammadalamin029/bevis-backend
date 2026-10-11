"""Rate limiting and brute-force lockout. Redis fixed-window counters.

Rules live here, not scattered across routes. The `client` parameter exists
so tests can pass a fake; production callers omit it and get shared Redis.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import redis

from config import redis as redis_config

# (path prefix, max requests, window seconds). First match wins.
RATE_LIMIT_RULES: tuple[tuple[str, int, int], ...] = (
    ("/api/auth/signin", 30, 60),
    ("/api/auth/signup", 10, 60),
    ("/api/auth/forgot-password", 5, 60),
    ("/api/auth/reset-password", 5, 60),
    ("/api/auth/resend-verification", 5, 60),
    ("/api/auth/verify-email", 10, 60),
    ("/api/users/delete", 5, 60),
)
DEFAULT_API_LIMIT = (200, 60)

# Brute force: this many bad passwords locks the email for the window.
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60

# Health and docs never count against anyone.
EXEMPT_PATHS = ("/health", "/", "/docs", "/openapi.json", "/redoc")


def _client(provided: redis.Redis | None) -> redis.Redis:
    return provided if provided is not None else redis_config.get_redis_client()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_allowance(
    key: str, limit: int, window_seconds: int, client: redis.Redis | None = None
) -> tuple[bool, int]:
    """Fixed-window check. Returns (allowed, seconds until reset)."""
    redis_client = _client(client)
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, window_seconds)
    ttl = redis_client.ttl(key)
    return count <= limit, max(0, ttl if ttl >= 0 else window_seconds)


def login_fail_key(email: str) -> str:
    return f"login_fail:{email.lower().strip()}"


def is_locked_out(email: str, client: redis.Redis | None = None) -> bool:
    redis_client = _client(client)
    raw = redis_client.get(login_fail_key(email))
    return raw is not None and int(raw) >= MAX_LOGIN_ATTEMPTS


def record_failed_login(email: str, client: redis.Redis | None = None) -> None:
    redis_client = _client(client)
    key = login_fail_key(email)
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, LOCKOUT_WINDOW_SECONDS)


def clear_failed_logins(email: str, client: redis.Redis | None = None) -> None:
    _client(client).delete(login_fail_key(email))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces RATE_LIMIT_RULES by client IP. Exempts health and docs."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXEMPT_PATHS or not path.startswith("/api"):
            return await call_next(request)

        rule = next(
            (r for r in RATE_LIMIT_RULES if path.startswith(r[0])), None
        )
        limit, window = (rule[1], rule[2]) if rule else DEFAULT_API_LIMIT
        allowed, retry_after = check_allowance(
            f"rl:{client_ip(request)}:{path}", limit, window
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Slow down."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
