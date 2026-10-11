"""Admin shapes. Everything here is require_admin-gated at the route."""

from pydantic import BaseModel, Field


class SettingUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=2000)


class PlanOut(BaseModel):
    name: str
    display_name: str
    max_projects: int
    max_repositories_per_project: int
    is_active: bool

    model_config = {"from_attributes": True}


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    display_name: str = Field(default="", max_length=120)
    max_projects: int = Field(ge=1, le=1000)
    max_repositories_per_project: int = Field(ge=1, le=100)


class PlanUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    max_projects: int | None = Field(default=None, ge=1, le=1000)
    max_repositories_per_project: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class UserPlanUpdate(BaseModel):
    plan_name: str = Field(min_length=1, max_length=60)


class StatsOut(BaseModel):
    total_users: int
    total_projects: int
    total_repositories: int
    total_posts_created: int
    verified_email_share: float
    posts_by_status: dict[str, int]
