"""Email verification codes: happy path, burn-out, cooldown."""

from fastapi.testclient import TestClient

from main import app
from models.user import User
from services import verification


def signup(client: TestClient, email: str) -> None:
    assert (
        client.post(
            "/api/auth/signup", json={"email": email, "password": "Password123!"}
        ).status_code
        == 201
    )


def headers_for(client: TestClient, email: str) -> dict:
    token = client.post(
        "/api/auth/signin", json={"email": email, "password": "Password123!"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def user_id_for(db_session, email: str) -> str:
    from sqlalchemy import select

    from models.user import User

    return db_session.scalar(select(User).where(User.email == email)).id


def test_verify_happy_path_flips_flag(db_session):
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        headers = headers_for(client, "ameenumhusah@gmail.com")
        code = verification.issue_code(
            user_id_for(db_session, "ameenumhusah@gmail.com")
        )
        response = client.post(
            "/api/auth/verify-email", json={"code": code}, headers=headers
        )
    assert response.status_code == 200, response.text
    assert (
        db_session.query(User)
        .filter_by(email="ameenumhusah@gmail.com")
        .one()
        .email_verified
        is True
    )


def test_five_misses_burn_the_code(db_session):
    uid = None
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        headers = headers_for(client, "ameen.dev09@gmail.com")
        uid = user_id_for(db_session, "ameen.dev09@gmail.com")
        code = verification.issue_code(uid)
        for _ in range(5):
            assert (
                client.post(
                    "/api/auth/verify-email", json={"code": "000000"}, headers=headers
                ).status_code
                == 400
            )
        # The sixth guess finds nothing, even with the right code.
        assert (
            client.post(
                "/api/auth/verify-email", json={"code": code}, headers=headers
            ).status_code
            == 400
        )


def test_resend_cooldown_and_already_verified(db_session):
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        headers = headers_for(client, "ameenumhusah@gmail.com")
        first = client.post("/api/auth/resend-verification", headers=headers)
        assert first.status_code == 200, first.text
        second = client.post("/api/auth/resend-verification", headers=headers)
        assert second.status_code == 429
        assert "Retry-After" in second.headers
