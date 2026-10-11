"""Admin surface: RBAC on every route, settings, plans, stats."""

from fastapi.testclient import TestClient

from main import app
from models.user import ROLE_ADMIN
from services.auth_service import create_user

ADMIN_PATHS = [
    ("GET", "/api/admin/settings"),
    ("PUT", "/api/admin/settings"),
    ("GET", "/api/admin/plans"),
    ("POST", "/api/admin/plans"),
    ("PUT", "/api/admin/plans/free"),
    ("PUT", "/api/admin/users/some-id/plan"),
    ("GET", "/api/admin/stats"),
]


def seed_admin(db_session, email: str = "ameenumhusah@gmail.com") -> None:
    try:
        create_user(db_session, email, "Password123!", role=ROLE_ADMIN)
    except Exception:
        pass


def headers_for(client: TestClient, email: str) -> dict:
    token = client.post(
        "/api/auth/signin",
        json={"email": email, "password": "Password123!"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def signup(client: TestClient, email: str) -> None:
    assert (
        client.post(
            "/api/auth/signup", json={"email": email, "password": "Password123!"}
        ).status_code
        == 201
    )


def test_customer_gets_403_everywhere(db_session):
    seed_admin(db_session)
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        headers = headers_for(client, "ameen.dev09@gmail.com")
        for method, path in ADMIN_PATHS:
            response = client.request(
                method, path, json={}, headers=headers
            )
            assert response.status_code == 403, (method, path)


def test_unauthenticated_gets_401():
    with TestClient(app) as client:
        assert client.get("/api/admin/stats").status_code == 401
        assert client.get("/api/admin/plans").status_code == 401


def test_settings_read_write_and_validation(db_session):
    seed_admin(db_session)
    with TestClient(app) as client:
        headers = headers_for(client, "ameenumhusah@gmail.com")
        assert client.get("/api/admin/settings", headers=headers).json() == {
            "max_repositories_per_project": "3"
        }
        assert (
            client.put(
                "/api/admin/settings",
                json={"key": "max_repositories_per_project", "value": "5"},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/admin/settings",
                json={"key": "nope", "value": "1"},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/admin/settings",
                json={"key": "max_repositories_per_project", "value": "many"},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/admin/settings",
                json={"key": "max_repositories_per_project", "value": "0"},
                headers=headers,
            ).status_code
            == 422
        )


def test_plans_crud_and_seat_protection(db_session):
    seed_admin(db_session)
    with TestClient(app) as client:
        headers = headers_for(client, "ameenumhusah@gmail.com")
        plans = client.get("/api/admin/plans", headers=headers).json()
        assert [p["name"] for p in plans] == ["free"]

        created = client.post(
            "/api/admin/plans",
            json={
                "name": "Pro",
                "display_name": "Pro",
                "max_projects": 20,
                "max_repositories_per_project": 10,
            },
            headers=headers,
        )
        assert created.status_code == 201
        assert created.json()["name"] == "pro"

        dupe = client.post(
            "/api/admin/plans",
            json={
                "name": "pro",
                "display_name": "Pro",
                "max_projects": 1,
                "max_repositories_per_project": 1,
            },
            headers=headers,
        )
        assert dupe.status_code == 409

        signup(client, "ameen.dev09@gmail.com")
        moved = client.put(
            "/api/admin/users/xxx/plan",
            json={"plan_name": "pro"},
            headers=headers,
        )
        assert moved.status_code == 404

        from config.database import SessionLocal

        db = SessionLocal()
        try:
            from models.user import User
            from sqlalchemy import select

            target = db.scalar(
                select(User).where(User.email == "ameen.dev09@gmail.com")
            )
            target_id = target.id
        finally:
            db.close()
        ok = client.put(
            f"/api/admin/users/{target_id}/plan",
            json={"plan_name": "pro"},
            headers=headers,
        )
        assert ok.status_code == 200
        assert ok.json()["plan_name"] == "pro"

        # Free still seats the admin: deactivation refused.
        stuck = client.put(
            "/api/admin/plans/free", json={"is_active": False}, headers=headers
        )
        assert stuck.status_code == 409

        # Pro seats one user too now: also refused.
        stuck2 = client.put(
            "/api/admin/plans/pro", json={"is_active": False}, headers=headers
        )
        assert stuck2.status_code == 409

        # Limits edit freely.
        edited = client.put(
            "/api/admin/plans/pro",
            json={"max_projects": 50},
            headers=headers,
        )
        assert edited.status_code == 200
        assert edited.json()["max_projects"] == 50

        # Unknown plan is 404, not 500.
        assert (
            client.put(
                "/api/admin/plans/nope", json={"max_projects": 1}, headers=headers
            ).status_code
            == 404
        )


def test_stats_reflect_reality(db_session):
    seed_admin(db_session)
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        headers = headers_for(client, "ameenumhusah@gmail.com")
        stats = client.get("/api/admin/stats", headers=headers).json()
    assert stats["total_users"] == 2
    assert stats["total_projects"] == 0
    assert stats["posts_by_status"] == {}
    assert stats["verified_email_share"] == 0.0
