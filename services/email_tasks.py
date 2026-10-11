"""Email delivery, worker side. Runs only inside Celery.

Retry policy (locked): exponential backoff, bounded retries, then log
recipient + template + reason and drop. No silent loss, no infinite backlog.
"""

import httpx
from celery import Task

from config.settings import settings
from services.email_templates import (
    post_ready_html,
    reset_html,
    verification_code_html,
    welcome_html,
)
from services.queue import celery_app
from utils.logger import get_logger

logger = get_logger("email")


def _post_to_sendlib(to: str, subject: str, html: str) -> None:
    if not settings.sendlib_api_key or not settings.sendlib_from:
        logger.warning(
            "sendlib not configured; dropping email to=%s subject=%s",
            to,
            subject,
        )
        return
    response = httpx.post(
        settings.sendlib_api_url,
        headers={"Authorization": f"Bearer {settings.sendlib_api_key}"},
        json={
            "from": settings.sendlib_from,
            "to": to,
            "subject": subject,
            "html": html,
        },
        timeout=30,
    )
    response.raise_for_status()


class SendEmailTask(Task):
    autoretry_for = (httpx.HTTPError,)
    max_retries = 5
    retry_backoff = True
    retry_backoff_max = 3600
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "email dropped after retries to=%s template=%s reason=%s",
            kwargs.get("to"),
            kwargs.get("template"),
            exc,
        )


@celery_app.task(base=SendEmailTask, bind=True, name="email.send")
def send_email(self, to: str, template: str, context: dict | None = None) -> None:
    """Render and deliver one email. Templates below, nothing else."""
    context = context or {}
    if template == "welcome":
        subject, html = welcome_html()
    elif template == "reset":
        subject, html = reset_html(context["reset_url"])
    elif template == "post_ready":
        subject, html = post_ready_html(
            context["project_name"], context.get("excerpt", "")
        )
    elif template == "verification":
        subject, html = verification_code_html(context["code"])
    elif template == "deletion":
        subject, html = deletion_code_html(context["code"])
    else:
        raise ValueError(f"unknown email template: {template}")
    _post_to_sendlib(to, subject, html)
