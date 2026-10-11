"""Cloudflare Turnstile verification. Signup route only.

No secret configured means verification is off (dev-safe). With a secret,
every signup must carry a valid token or it dies with a 400.
"""

import httpx

from config.settings import settings
from utils.logger import get_logger

logger = get_logger("captcha")


def verify_captcha(token: str | None) -> bool:
    """True when verification is off or Cloudflare says success."""
    if not settings.turnstile_secret_key:
        return True
    if not token:
        return False
    try:
        response = httpx.post(
            settings.turnstile_verify_url,
            data={
                "secret": settings.turnstile_secret_key,
                "response": token,
            },
            timeout=10,
        )
        response.raise_for_status()
        return bool(response.json().get("success", False))
    except Exception as exc:
        logger.warning("turnstile verification failed: %s", exc)
        return False
