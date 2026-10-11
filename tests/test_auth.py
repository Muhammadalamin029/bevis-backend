"""Milestone 2: signup, signin, me, RBAC gates, env admin seeding."""

from fastapi.testclient import TestClient

from main import app
from models.user import ROLE_ADMIN, ROLE_CUSTOMER
from services.auth_service import create_user, ensure_admin_from_env


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def signup(client: TestClient, email: str, password: str = "Password123!") -> dict:
    response = client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


def signin(client: TestClient, email: str, password: str = "Password123!") -> dict:
    response = client.post(
        "/api/auth/signin", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_signup_creates_customer_with_profile():
    with TestClient(app) as client:
        body = signup(client, "ameenumhusah@gmail.com")
    assert body["email"] == "ameenumhusah@gmail.com"
    assert body["role"] == ROLE_CUSTOMER
    assert body["id"]


def test_signup_rejects_duplicates_and_bad_input():
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        assert (
            client.post(
                "/api/auth/signup",
                json={"email": "ameen.dev09@gmail.com", "password": "Password123!"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/auth/signup",
                json={"email": "ameenumhusah@gmail", "password": "Password123!"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/auth/signup", json={"email": "ameen.dev09@gmail.com", "password": "short"}
            ).status_code
            == 422
        )


def test_signin_me_roundtrip():
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        token = signin(client, "ameenumhusah@gmail.com")["access_token"]
        me = client.get("/api/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "ameenumhusah@gmail.com"


def test_signin_rejects_wrong_password():
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        response = client.post(
            "/api/auth/signin",
            json={"email": "ameen.dev09@gmail.com", "password": "Wrongpass1!"},
        )
    assert response.status_code == 401


def test_me_rejects_missing_and_tampered_tokens():
    with TestClient(app) as client:
        assert client.get("/api/auth/me").status_code == 401
        assert (
            client.get(
                "/api/auth/me", headers=auth_headers("tampered.token.here")
            ).status_code
            == 401
        )


def test_admin_seed_is_idempotent(db_session):
    from config.settings import settings

    settings.admin_email = "ameenumhusah@gmail.com"
    settings.admin_password = "Supersecret1!"
    try:
        first = ensure_admin_from_env(db_session)
        second = ensure_admin_from_env(db_session)
        assert first is not None and second is not None
        assert first.id == second.id
        assert first.role == ROLE_ADMIN
    finally:
        settings.admin_email = ""
        settings.admin_password = ""


def test_require_admin_blocks_customers(db_session):
    from fastapi import HTTPException

    from routes.deps import require_admin

    customer = create_user(db_session, "ameenumhusah@gmail.com", "Password123!")
    admin = create_user(db_session, "ameen.dev09@gmail.com", "Password123!")
    admin.role = ROLE_ADMIN

    assert require_admin(admin).id == admin.id
    try:
        require_admin(customer)
        blocked = False
    except HTTPException as exc:
        blocked = exc.status_code == 403
    assert blocked
