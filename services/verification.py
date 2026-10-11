"""One-time codes in Redis. Email verification and account deletion
share mechanics, never keys: each purpose has its own namespace so a
code for one job can never unlock the other.

A 6-digit code is guessable, so three things contain it: a 10-minute
TTL, five attempts max, and per-request rate limiting at the route.
"""

import hashlib
import secrets

import redis

from config import redis as redis_config

CODE_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

PURPOSE_VERIFY = "verify"
PURPOSE_DELETE = "delete"


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _client(provided: redis.Redis | None) -> redis.Redis:
    return provided if provided is not None else redis_config.get_redis_client()


def issue_code(
    user_id: str, client: redis.Redis | None = None, purpose: str = PURPOSE_VERIFY
) -> str:
    """Mint a fresh code, wiping any previous one. Returns raw digits."""
    redis_client = _client(client)
    code = f"{secrets.randbelow(1_000_000):06d}"
    pipe = redis_client.pipeline()
    pipe.set(f"{purpose}:{user_id}", _hash(code), ex=CODE_TTL_SECONDS)
    pipe.delete(f"{purpose}_attempts:{user_id}")
    pipe.set(f"{purpose}_cooldown:{user_id}", "1", ex=RESEND_COOLDOWN_SECONDS)
    pipe.execute()
    return code


def on_cooldown(
    user_id: str, client: redis.Redis | None = None, purpose: str = PURPOSE_VERIFY
) -> bool:
    return (
        _client(client).exists(f"{purpose}_cooldown:{user_id}") == 1
    )


def cooldown_seconds_left(
    user_id: str, client: redis.Redis | None = None, purpose: str = PURPOSE_VERIFY
) -> int:
    ttl = _client(client).ttl(f"{purpose}_cooldown:{user_id}")
    return max(0, ttl if ttl and ttl > 0 else 0)


def check_code(
    user_id: str,
    code: str,
    client: redis.Redis | None = None,
    purpose: str = PURPOSE_VERIFY,
) -> bool:
    """One guess. True consumes the code; five misses burn it."""
    redis_client = _client(client)
    attempts = redis_client.incr(f"{purpose}_attempts:{user_id}")
    if attempts == 1:
        redis_client.expire(f"{purpose}_attempts:{user_id}", CODE_TTL_SECONDS)
    if attempts > MAX_ATTEMPTS:
        redis_client.delete(f"{purpose}:{user_id}")
        return False
    stored = redis_client.get(f"{purpose}:{user_id}")
    if stored is None or stored != _hash(code.strip()):
        return False
    redis_client.delete(f"{purpose}:{user_id}")
    redis_client.delete(f"{purpose}_attempts:{user_id}")
    return True
