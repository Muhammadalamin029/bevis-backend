"""Liveness plus dependency connectivity. The deploy healthcheck hits here."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.database import get_db
from config import redis as redis_config
from config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    try:
        redis_config.get_redis_client().ping()
        redis_status = "connected"
    except Exception:
        redis_status = "down"
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "database": "connected",
        "redis": redis_status,
    }
