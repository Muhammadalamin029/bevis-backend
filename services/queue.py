"""Celery application. Neutral infrastructure: tasks register here,
workloads live in services.*_tasks modules. Broker and result backend
default to the session Redis; point them elsewhere via env when the
queue outgrows company."""

from celery import Celery

from config.settings import settings


def build_celery_app() -> Celery:
    broker = settings.celery_broker_url or settings.redis_url
    backend = settings.celery_result_backend or settings.redis_url
    app = Celery(
        "bevis",
        broker=broker,
        backend=backend,
        include=["services.email_tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = build_celery_app()
