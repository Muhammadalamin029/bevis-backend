"""Service layer. One module per domain, added as milestones land."""

from services.app_settings import (
    EDITABLE_SETTINGS,
    get_max_repositories_per_project,
    get_setting,
    set_setting,
)
from services.plans import (
    can_create_project,
    create_plan,
    get_plan,
    list_plans,
    plan_for_user,
    set_user_plan,
    update_plan,
    user_project_count,
)
from services.stats import (
    read_site_stats,
    record_post_created,
    record_project_created,
    record_repository_connected,
    record_user_created,
)

__all__ = [
    "EDITABLE_SETTINGS",
    "can_create_project",
    "create_plan",
    "get_max_repositories_per_project",
    "get_plan",
    "get_setting",
    "list_plans",
    "plan_for_user",
    "read_site_stats",
    "record_post_created",
    "record_project_created",
    "record_repository_connected",
    "record_user_created",
    "set_setting",
    "set_user_plan",
    "update_plan",
    "user_project_count",
]
