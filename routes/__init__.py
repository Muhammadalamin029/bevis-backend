"""Route registration. Routers are added here as each milestone lands."""

from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.github import router as github_router
from routes.health import router as health_router
from routes.projects import router as projects_router
from routes.users import router as users_router

__all__ = ["admin_router", "auth_router", "health_router", "users_router"]
