"""Logout: single session burn and burn-everywhere."""

from fastapi.testclient import TestClient

from main import app


def signup(client: TestClient, email: str) -> None:
    assert (
        client.post(
            "/api/auth/signup", json={"email": email, "password": "Password123!"}
        ).status_code
        == 201
    )


def signin_pair(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/auth/signin", json={"email": email, "password": "Password123!"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_logout_burns_one_session_but_spares_the_other():
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        first = signin_pair(client, "ameenumhusah@gmail.com")
        second = signin_pair(client, "ameenumhusah@gmail.com")

        assert (
            client.post(
                "/api/auth/logout",
                json={"refresh_token": first["refresh_token"]},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/auth/refresh",
                json={"refresh_token": first["refresh_token"]},
            ).status_code
            == 401
        )
        # The other session survives.
        assert (
            client.post(
                "/api/auth/refresh",
                json={"refresh_token": second["refresh_token"]},
            ).status_code
            == 200
        )


def test_logout_is_best_effort_without_a_token():
    with TestClient(app) as client:
        assert client.post("/api/auth/logout", json={}).status_code == 200
        assert (
            client.post(
                "/api/auth/logout", json={"refresh_token": "garbage"}
            ).status_code
            == 200
        )


def test_logout_all_burns_every_session():
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        first = signin_pair(client, "ameen.dev09@gmail.com")
        second = signin_pair(client, "ameen.dev09@gmail.com")
        headers = {"Authorization": f"Bearer {first['access_token']}"}

        assert (
            client.post("/api/auth/logout-all", headers=headers).status_code == 200
        )
        for pair in (first, second):
            assert (
                client.post(
                    "/api/auth/refresh",
                    json={"refresh_token": pair["refresh_token"]},
                ).status_code
                == 401
            )


def test_logout_all_requires_auth():
    with TestClient(app) as client:
        assert client.post("/api/auth/logout-all").status_code == 401
