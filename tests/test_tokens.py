"""Refresh rotation, forgot/reset, change password. Redis is faked."""

import pytest
from fastapi.testclient import TestClient

from main import app


def signup(client: TestClient, email: str, password: str = "Password123!") -> dict:
    response = client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_refresh_rotates_and_burns_the_old_token(fake_redis):
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        pair = client.post(
            "/api/auth/signin",
            json={"email": "ameenumhusah@gmail.com", "password": "Password123!"},
        ).json()
        assert "refresh_token" in pair

        rotated = client.post(
            "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        )
        assert rotated.status_code == 200, rotated.text
        assert rotated.json()["refresh_token"] != pair["refresh_token"]

        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {rotated.json()['access_token']}"},
        )
        assert me.status_code == 200

        replay = client.post(
            "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        )
        assert replay.status_code == 401


def test_refresh_rejects_garbage(fake_redis):
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": "nope-not-real"}
        )
        assert response.status_code == 401


def test_forgot_always_returns_200(fake_redis, db_session):
    from services.auth_service import request_password_reset

    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        assert (
            client.post(
                "/api/auth/forgot-password", json={"email": "ameen.dev09@gmail.com"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/auth/forgot-password", json={"email": "ameenumhusah@gmail.com"}
            ).status_code
            == 200
        )
    # Unknown emails mint nothing to steal.
    assert request_password_reset(db_session, "ameenumhusah@gmail.com") is None


def test_reset_flow_and_single_use(fake_redis, db_session):
    from services.auth_service import request_password_reset

    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com", "Oldpassword1!")
        token = request_password_reset(db_session, "ameen.dev09@gmail.com")
        assert token is not None

        assert (
            client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "Brandnewpass1!"},
            ).status_code
            == 200
        )
        # Reuse is dead.
        assert (
            client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "Anotherpass1!"},
            ).status_code
            == 400
        )
        # Garbage is dead.
        assert (
            client.post(
                "/api/auth/reset-password",
                json={"token": "garbage", "new_password": "Anotherpass1!"},
            ).status_code
            == 400
        )
        # New password works, old one doesn't.
        assert (
            client.post(
                "/api/auth/signin",
                json={"email": "ameen.dev09@gmail.com", "password": "Brandnewpass1!"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/auth/signin",
                json={"email": "ameen.dev09@gmail.com", "password": "Oldpassword1!"},
            ).status_code
            == 401
        )


def test_change_password_needs_current_and_burns_sessions(fake_redis):
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com", "Oldpassword1!")
        pair = client.post(
            "/api/auth/signin",
            json={"email": "ameenumhusah@gmail.com", "password": "Oldpassword1!"},
        ).json()
        headers = {"Authorization": f"Bearer {pair['access_token']}"}

        bad = client.post(
            "/api/auth/change-password",
            json={"current_password": "Wrongpass1!", "new_password": "Newpassword1!"},
            headers=headers,
        )
        assert bad.status_code == 400

        good = client.post(
            "/api/auth/change-password",
            json={"current_password": "Oldpassword1!", "new_password": "Newpassword1!"},
            headers=headers,
        )
        assert good.status_code == 200

        # Old password dead, new works, old refresh burned with the change.
        assert (
            client.post(
                "/api/auth/signin",
                json={"email": "ameenumhusah@gmail.com", "password": "Oldpassword1!"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/signin",
                json={"email": "ameenumhusah@gmail.com", "password": "Newpassword1!"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/auth/refresh",
                json={"refresh_token": pair["refresh_token"]},
            ).status_code
            == 401
        )
