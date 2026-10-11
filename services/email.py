"""Route-side email API. Everything here enqueues and returns.

Nothing in this module sends mail. Delivery happens in the worker
(services.email_tasks); these helpers only shape the task payload.
"""

from config.settings import settings
from services.email_tasks import send_email


def queue_welcome_email(to: str) -> None:
    send_email.delay(to=to, template="welcome", context={})


def queue_password_reset_email(to: str, token: str) -> None:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    send_email.delay(to=to, template="reset", context={"reset_url": reset_url})


def queue_post_ready_email(to: str, project_name: str, excerpt: str = "") -> None:
    send_email.delay(
        to=to,
        template="post_ready",
        context={"project_name": project_name, "excerpt": excerpt},
    )


def queue_verification_email(to: str, code: str) -> None:
    send_email.delay(to=to, template="verification", context={"code": code})


def queue_deletion_email(to: str, code: str) -> None:
    send_email.delay(to=to, template="deletion", context={"code": code})
