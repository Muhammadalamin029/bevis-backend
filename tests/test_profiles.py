"""Profiles, onboarding, and self-deletion."""

from fastapi.testclient import TestClient

from main import app


def signup(client: TestClient, email: str, password: str = "Password123!") -> dict:
    response = client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


def token_for(client: TestClient, email: str, password: str = "Password123!") -> str:
    return client.post(
        "/api/auth/signin", json={"email": email, "password": password}
    ).json()["access_token"]


def test_read_own_profile():
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        headers = {"Authorization": f"Bearer {token_for(client, 'ameenumhusah@gmail.com')}"}
        response = client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] is None


def test_patch_profile_fields_together():
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        headers = {"Authorization": f"Bearer {token_for(client, 'ameen.dev09@gmail.com')}"}
        response = client.patch(
            "/api/users/me",
            json={
                "display_name": "Ada Pusher",
                "headline": "Frontend Developer",
                "bio": "Ships things.",
                "username": "Ada_Pusher",
            },
            headers=headers,
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == "ada_pusher"
    assert body["headline"] == "Frontend Developer"
    assert body["display_name"] == "Ada Pusher"


def test_username_clash_is_409_and_shape_is_400():
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        signup(client, "ameen.dev09@gmail.com")
        h1 = {"Authorization": f"Bearer {token_for(client, 'ameenumhusah@gmail.com')}"}
        h2 = {"Authorization": f"Bearer {token_for(client, 'ameen.dev09@gmail.com')}"}
        assert (
            client.patch("/api/users/me", json={"username": "taken"}, headers=h1)
        ).status_code == 200
        clash = client.patch(
            "/api/users/me", json={"username": "TAKEN"}, headers=h2
        )
        assert clash.status_code == 409
        bad = client.patch(
            "/api/users/me", json={"username": "has space!"}, headers=h2
        )
        assert bad.status_code == 400


def test_onboarding_once():
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        headers = {"Authorization": f"Bearer {token_for(client, 'ameenumhusah@gmail.com')}"}
        first = client.post(
            "/api/users/onboarding",
            json={"username": "boardie", "headline": "Backend Developer"},
            headers=headers,
        )
        assert first.status_code == 200, first.text
        me = client.get("/api/auth/me", headers=headers).json()
        assert me["onboarding_completed"] is True
        again = client.post(
            "/api/users/onboarding",
            json={"username": "other", "headline": "x"},
            headers=headers,
        )
        assert again.status_code == 400


def test_delete_account_staged_flow(db_session):
    from sqlalchemy import func, select

    from models.profile import Profile
    from models.user import User
    from models.user_stats import UserStats
    from services import verification
    from services.verification import PURPOSE_DELETE

    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        headers = {"Authorization": f"Bearer {token_for(client, 'ameen.dev09@gmail.com')}"}
        # Step 1 rejects a wrong password and issues nothing.
        wrong = client.post(
            "/api/users/delete/request",
            json={"current_password": "Nottheright1!"},
            headers=headers,
        )
        assert wrong.status_code == 400
        # Right password issues the OTP (fetch it like the mailbox would).
        asked = client.post(
            "/api/users/delete/request",
            json={"current_password": "Password123!"},
            headers=headers,
        )
        assert asked.status_code == 200, asked.text
        user_id = db_session.scalar(
            select(User).where(User.email == "ameen.dev09@gmail.com")
        ).id
        raw = verification.issue_code(user_id, purpose=PURPOSE_DELETE)
        # Step 2 rejects a wrong code, accepts the right one.
        assert (
            client.post(
                "/api/users/delete/confirm", json={"code": "000000"}, headers=headers
            ).status_code
            == 400
        )
        gone = client.post(
            "/api/users/delete/confirm", json={"code": raw}, headers=headers
        )
        assert gone.status_code == 200, gone.text
        assert (
            client.get("/api/auth/me", headers=headers).status_code == 401
        )

    assert db_session.query(User).count() == 0
    assert db_session.query(Profile).count() == 0
    assert db_session.query(UserStats).count() == 0
    assert (
        db_session.scalar(select(func.count()).select_from(UserStats)) == 0
    )
