"""Rate limiting and brute-force lockout. Redis is faked."""

from fastapi.testclient import TestClient

from main import app
from services.auth_service import decode_access_token


def signup(client: TestClient, email: str, password: str = "Password123!") -> None:
    response = client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text


def test_signin_rate_limit_returns_429_with_retry_after():
    with TestClient(app) as client:
        statuses = [
            client.post(
                "/api/auth/signin",
                json={"email": f"ameenumhusah+t{i}@gmail.com", "password": "Wrongpass1!"},
            ).status_code
            for i in range(32)
        ]
    assert statuses[:30] == [401] * 30
    assert statuses[30] == 429
    assert statuses[31] == 429


def test_lockout_blocks_even_the_right_password():
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        for _ in range(5):
            assert (
                client.post(
                    "/api/auth/signin",
                    json={"email": "ameenumhusah@gmail.com", "password": "Wrongpass1!"},
                ).status_code
                == 401
            )
        locked = client.post(
            "/api/auth/signin",
            json={"email": "ameenumhusah@gmail.com", "password": "Password123!"},
        )
        assert locked.status_code == 429
        assert "Retry-After" in locked.headers


def test_few_failures_then_success_resets_the_counter():
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        for _ in range(4):
            client.post(
                "/api/auth/signin",
                json={"email": "ameen.dev09@gmail.com", "password": "Wrongpass1!"},
            )
        good = client.post(
            "/api/auth/signin",
            json={"email": "ameen.dev09@gmail.com", "password": "Password123!"},
        )
        assert good.status_code == 200
        # Counter cleared: four more failures stay 401s, not a lockout.
        statuses = [
            client.post(
                "/api/auth/signin",
                json={"email": "ameen.dev09@gmail.com", "password": "Wrongpass1!"},
            ).status_code
            for _ in range(4)
        ]
        assert statuses == [401] * 4


def test_access_tokens_live_about_an_hour():
    from datetime import datetime, timezone

    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        token = client.post(
            "/api/auth/signin",
            json={"email": "ameenumhusah@gmail.com", "password": "Password123!"},
        ).json()["access_token"]
    payload = decode_access_token(token)
    assert payload is not None
    lifetime = (
        datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        - datetime.now(timezone.utc)
    ).total_seconds()
    assert 55 * 60 < lifetime <= 60 * 60
