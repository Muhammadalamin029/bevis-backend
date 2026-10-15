"""GitHub App integration. App JWT, installation tokens, repo listing,
webhook signatures. No OAuth user flow: the App model carries everything."""

import hashlib
import hmac
import time
from pathlib import Path

import httpx
import jwt

from config.settings import settings
from models.github_installation import GitHubInstallation
from models.user import User
from sqlalchemy import select
from sqlalchemy.orm import Session
from utils.logger import get_logger

logger = get_logger("github")

# installation_id -> (token, expires_at_epoch). Process-local is fine:
# tokens are short-lived and re-fetching is cheap and safe.
_token_cache: dict[int, tuple[str, float]] = {}


def configured() -> bool:
    """False when GitHub features must refuse cleanly instead of crashing."""
    return bool(
        settings.github_app_id
        and (settings.github_private_key or settings.github_private_key_file)
        and settings.github_webhook_secret
    )


def _private_key() -> str:
    if settings.github_private_key_file:
        return Path(settings.github_private_key_file).read_text()
    return settings.github_private_key.replace("\\n", "\n")


def app_jwt(now: float | None = None) -> str:
    """Short-lived App JWT for app-level API calls (max 10 minutes)."""
    timestamp = int(now if now is not None else time.time())
    return jwt.encode(
        {"iat": timestamp - 60, "exp": timestamp + 9 * 60, "iss": settings.github_app_id},
        _private_key(),
        algorithm="RS256",
    )


def installation_token(installation_id: int) -> str:
    """Short-lived installation token, cached until a minute before expiry."""
    cached = _token_cache.get(installation_id)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    response = httpx.post(
        f"{settings.github_api_url}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt()}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload["token"]
    expires_at = _token_cache_token_expiry(payload.get("expires_at", ""))
    _token_cache[installation_id] = (token, expires_at)
    # Bound the cache: installations come and go.
    if len(_token_cache) > 1000:
        _token_cache.clear()
    return token


def _token_cache_token_expiry(expires_at: str) -> float:
    from datetime import datetime, timezone

    try:
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time() + 50 * 60


def list_installation_repositories(installation_id: int) -> list[dict]:
    """Repos the installation can access. Paginates to the end."""
    token = installation_token(installation_id)
    repos: list[dict] = []
    url: str | None = f"{settings.github_api_url}/installation/repositories?per_page=100"
    while url:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        repos.extend(payload.get("repositories", []))
        links = response.headers.get("Link", "")
        url = _next_link(links)
    return repos


def _next_link(link_header: str) -> str | None:
    for part in link_header.split(","):
        segments = part.strip().split(";")
        if len(segments) == 2 and 'rel="next"' in segments[1]:
            return segments[0].strip().strip("<>")
    return None


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """HMAC-SHA256 check. Missing or wrong signatures fail closed."""
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.github_webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


def install_url() -> str:
    return f"https://github.com/apps/{settings.github_app_slug}/installations/new"


def user_installation(db: Session, user: User) -> GitHubInstallation | None:
    return db.scalar(
        select(GitHubInstallation).where(GitHubInstallation.user_id == user.id)
    )
