"""Bevis API entrypoint. Schema is owned by Alembic, never created here."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.database import SessionLocal
from config.settings import settings
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.health import router as health_router
from routes.users import router as users_router
from services.auth_service import ensure_admin_from_env
from services.rate_limit import RateLimitMiddleware
from utils.logger import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        admin = ensure_admin_from_env(db)
        if admin is not None:
            logger.info("admin account ready: %s", admin.email)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.add_middleware(RateLimitMiddleware)


@app.get("/")
def first_route() -> dict:
    return {"message": f"{settings.app_name} API. Don't say it. Show proof."}
