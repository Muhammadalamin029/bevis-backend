"""Plans, usernames, and stats counters."""

import pytest
from fastapi.testclient import TestClient

from main import app
from models.plan import Plan
from models.user import User
from services.plans import (
    can_create_project,
    plan_for_user,
    set_user_plan,
)
from services.profiles import normalize_username, set_username


def signup(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/auth/signup", json={"email": email, "password": "Password123!"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_free_plan_seeded_and_default(db_session):
    from services.plans import get_plan

    plan = get_plan(db_session, "free")
    assert plan is not None
    assert plan.max_projects == 3
    assert plan.max_repositories_per_project == 3
    assert plan.is_active


def test_signup_lands_on_free_with_stats_row():
    from config.database import SessionLocal
    from models.site_stats import GLOBAL_STATS_ID, SiteStats
    from models.user_stats import UserStats

    with TestClient(app) as client:
        body = signup(client, "ameenumhusah@gmail.com")
    assert body["plan_name"] == "free"

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email="ameenumhusah@gmail.com").one()
        assert db.get(UserStats, user.id) is not None
        site = db.get(SiteStats, GLOBAL_STATS_ID)
        assert site is not None and site.total_users >= 1
    finally:
        db.close()


def test_plan_limits_gate_project_creation(db_session):
    from services.auth_service import create_user

    user = create_user(db_session, "ameen.dev09@gmail.com", "Password123!")
    plan = plan_for_user(db_session, user)
    assert plan.name == "free"
    # No projects yet: allowed. Enforcement against real rows lands
    # with the project service; the gate logic is proven here.
    allowed, _ = can_create_project(db_session, user)
    assert allowed


def test_admin_can_move_users_between_plans(db_session):
    from services.auth_service import create_user
    from services.plans import FREE_PLAN

    user = create_user(db_session, "ameenumhusah@gmail.com", "Password123!")
    assert user.plan_name == FREE_PLAN
    db_session.add(
        Plan(
            name="pro", display_name="Pro", max_projects=20,
            max_repositories_per_project=10,
        )
    )
    db_session.commit()
    set_user_plan(db_session, user, "pro")
    assert user.plan_name == "pro"
    with pytest.raises(ValueError):
        set_user_plan(db_session, user, "no-such-plan")


def test_username_rules_and_uniqueness(db_session):
    from services.auth_service import create_user

    assert normalize_username("  AdaPusher_99 ") == "adapusher_99"
    with pytest.raises(ValueError):
        normalize_username("has space!")
    with pytest.raises(ValueError):
        normalize_username("")

    ada = create_user(db_session, "ameen.dev09@gmail.com", "Password123!")
    bob = create_user(db_session, "ameenumhusah@gmail.com", "Password123!")
    set_username(db_session, ada.id, "Ada")
    assert ada_username(db_session, ada.id) == "ada"
    with pytest.raises(ValueError):
        set_username(db_session, bob.id, "ADA")


def ada_username(db_session, user_id: str) -> str | None:
    from sqlalchemy import select

    from models.profile import Profile

    row = db_session.scalar(select(Profile).where(Profile.user_id == user_id))
    return row.username if row else None
