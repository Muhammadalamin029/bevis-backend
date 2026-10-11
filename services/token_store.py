"""Refresh-token storage in Redis. Opaque tokens, SHA256 hashes as keys.

Key scheme:
  refresh:{sha256}      -> user_id, EXPIRE = refresh TTL (rotate/revoke = DEL)
  user_refresh:{user_id} -> SET of hashes, same TTL (revoke-all support)

Only hashes touch Redis. The `client` parameter exists so tests can pass
a fake; production callers omit it and get the shared client.
"""

import hashlib
import secrets

import redis

from config import redis as redis_config
from config.settings import settings


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ttl_seconds() -> int:
    return settings.refresh_token_expire_days * 24 * 3600


def _client(provided: redis.Redis | None) -> redis.Redis:
    return provided if provided is not None else redis_config.get_redis_client()


def new_token() -> str:
    return secrets.token_urlsafe(48)


def issue(user_id: str, client: redis.Redis | None = None) -> str:
    """Create a refresh token. Returns the raw token (shown once)."""
    redis_client = _client(client)
    token = new_token()
    digest = _hash(token)
    pipe = redis_client.pipeline()
    pipe.set(f"refresh:{digest}", user_id, ex=_ttl_seconds())
    pipe.sadd(f"user_refresh:{user_id}", digest)
    pipe.expire(f"user_refresh:{user_id}", _ttl_seconds())
    pipe.execute()
    return token


def lookup(token: str, client: redis.Redis | None = None) -> str | None:
    """Return the user_id for a live token, else None."""
    return _client(client).get(f"refresh:{_hash(token)}")


def revoke(token: str, client: redis.Redis | None = None) -> None:
    """Burn one token (rotation and single logout)."""
    redis_client = _client(client)
    digest = _hash(token)
    user_id = redis_client.get(f"refresh:{digest}")
    pipe = redis_client.pipeline()
    pipe.delete(f"refresh:{digest}")
    if user_id:
        pipe.srem(f"user_refresh:{user_id}", digest)
    pipe.execute()


def revoke_all_for_user(user_id: str, client: redis.Redis | None = None) -> None:
    """Burn every session (password change/reset)."""
    redis_client = _client(client)
    digests = redis_client.smembers(f"user_refresh:{user_id}")
    pipe = redis_client.pipeline()
    for digest in digests:
        pipe.delete(f"refresh:{digest}")
    pipe.delete(f"user_refresh:{user_id}")
    pipe.execute()


def _reset_ttl_seconds() -> int:
    return settings.reset_token_expire_minutes * 60


def issue_reset(user_id: str, client: redis.Redis | None = None) -> str:
    """Create a single-use reset token. Returns the raw token (shown once)."""
    redis_client = _client(client)
    token = new_token()
    redis_client.set(
        f"reset:{_hash(token)}", user_id, ex=_reset_ttl_seconds()
    )
    return token


def consume_reset(token: str, client: redis.Redis | None = None) -> str | None:
    """Atomically take a reset token. Second use finds nothing."""
    return _client(client).getdel(f"reset:{_hash(token)}")
