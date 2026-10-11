"""Password policy: 8+, upper, lower, special. Every entry point."""

from fastapi.testclient import TestClient

from main import app
from services.auth_service import check_password_strength


def test_policy_spells_out_each_missing_class():
    assert check_password_strength("Password123!") is None
    assert "8 characters" in (check_password_strength("Pw1!") or "")
    assert "uppercase" in (check_password_strength("password123!") or "")
    assert "lowercase" in (check_password_strength("PASSWORD123!") or "")
    assert "special" in (check_password_strength("Password123") or "")


def test_signup_rejects_weak_passwords():
    with TestClient(app) as client:
        for i, weak in enumerate(
            ["short1!", "alllowercase1!", "ALLUPPERCASE1!", "NoSpecial123"]
        ):
            response = client.post(
                "/api/auth/signup",
                json={"email": f"weak{i}@gmail.com", "password": weak},
            )
            assert response.status_code == 422, (weak, response.text)


def test_reset_and_change_enforce_the_same_rule():
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/auth/signup",
                json={
                    "email": "ameenumhusah@gmail.com",
                    "password": "Password123!",
                },
            ).status_code
            == 201
        )
        token = client.post(
            "/api/auth/signin",
            json={"email": "ameenumhusah@gmail.com", "password": "Password123!"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        from services.auth_service import request_password_reset
        from config.database import SessionLocal

        db = SessionLocal()
        try:
            reset_token = request_password_reset(db, "ameenumhusah@gmail.com")
        finally:
            db.close()
        assert reset_token is not None

        # Weak new password dies at every gate with 422.
        assert (
            client.post(
                "/api/auth/reset-password",
                json={"token": reset_token, "new_password": "weakpass1"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "Password123!",
                    "new_password": "weakpass1",
                },
                headers=headers,
            ).status_code
            == 422
        )
