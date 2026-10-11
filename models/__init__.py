"""Import every model here so Base.metadata covers all tables."""

from models.app_setting import AppSetting
from models.generated_post import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    GeneratedPost,
)
from models.github_installation import GitHubInstallation
from models.plan import Plan
from models.profile import Profile
from models.project import Project
from models.push_event import PushEvent
from models.repository import Repository
from models.site_stats import GLOBAL_STATS_ID, SiteStats
from models.user import User
from models.user_stats import UserStats

__all__ = [
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_PROCESSING",
    "GLOBAL_STATS_ID",
    "AppSetting",
    "GeneratedPost",
    "GitHubInstallation",
    "Plan",
    "Profile",
    "Project",
    "PushEvent",
    "Repository",
    "SiteStats",
    "User",
    "UserStats",
]
