"""GitHub App milestone: install, repos, attach, webhook intake."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from config.settings import settings
from main import app
from models.project import Project
from services import github_service


@pytest.fixture()
def github_configured(monkeypatch):
    monkeypatch.setattr(settings, "github_app_id", "12345")
    monkeypatch.setattr(settings, "github_app_slug", "bevis-test")
    monkeypatch.setattr(settings, "github_private_key", "not-a-real-key")
    monkeypatch.setattr(settings, "github_webhook_secret", "test-secret")
    monkeypatch.setattr(
        github_service, "app_jwt", lambda now=None: "fake-app-jwt"
    )
    github_service._token_cache.clear()
    return settings


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


def make_project(db_session, owner_id: str, name: str = "Shop") -> str:
    project = Project(owner_id=owner_id, name=name, description="")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def user_id_for(db_session, email: str) -> str:
    from sqlalchemy import select

    from models.user import User

    return db_session.scalar(select(User).where(User.email == email)).id


REPOS = [
    {"id": 111, "full_name": "ada/shop-frontend", "private": False},
    {"id": 222, "full_name": "ada/shop-backend", "private": True},
]


class FakeResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def mock_github_api(monkeypatch, repos=None):
    def fake_post(url, **kwargs):
        assert "access_tokens" in url
        return FakeResponse({"token": "install-token", "expires_at": "2099-01-01T00:00:00Z"})

    def fake_get(url, **kwargs):
        return FakeResponse({"repositories": repos if repos is not None else REPOS})

    monkeypatch.setattr(github_service.httpx, "post", fake_post)
    monkeypatch.setattr(github_service.httpx, "get", fake_get)


def signed_push(secret: str, repo_id: int, ref: str = "refs/heads/main"):
    import hashlib
    import hmac
    import json

    payload = json.dumps(
        {
            "ref": ref,
            "repository": {"id": repo_id},
            "head_commit": {"id": "abc123"},
            "commits": [{"id": "abc123", "message": "ship it"}],
        }
    ).encode()
    signature = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return payload, signature


def test_unconfigured_github_refuses_cleanly(monkeypatch):
    monkeypatch.setattr(settings, "github_app_id", "")
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        headers = headers_for(client, "ameenumhusah@gmail.com")
        assert client.get("/api/github/install-url", headers=headers).status_code == 503
        assert (
            client.post(
                "/api/github/webhook",
                content=b"{}",
                headers={"X-Hub-Signature-256": "sha256=0", "X-GitHub-Event": "push"},
            ).status_code
            == 401
        )


def test_install_callback_and_repo_listing(github_configured, monkeypatch, db_session):
    mock_github_api(monkeypatch)
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        headers = headers_for(client, "ameen.dev09@gmail.com")
        install = client.get("/api/github/install-url", headers=headers).json()
        assert "bevis-test" in install["install_url"]
        callback = client.post(
            "/api/github/installations",
            json={"installation_id": 999},
            headers=headers,
        )
        assert callback.status_code == 200
        repos = client.get("/api/github/repositories", headers=headers).json()
        assert [r["github_repo_id"] for r in repos] == [111, 222]


def test_attach_flow_cap_and_duplicates(github_configured, monkeypatch, db_session):
    mock_github_api(monkeypatch)
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        headers = headers_for(client, "ameenumhusah@gmail.com")
        client.post(
            "/api/github/installations",
            json={"installation_id": 999},
            headers=headers,
        )
        project_id = make_project(
            db_session, user_id_for(db_session, "ameenumhusah@gmail.com")
        )
        first = client.post(
            f"/api/projects/{project_id}/repositories",
            json={"github_repo_id": 111, "role": "frontend", "tracked_branch": "main"},
            headers=headers,
        )
        assert first.status_code == 201, first.text
        assert "AI model" in first.json()["notice"]
        dupe = client.post(
            f"/api/projects/{project_id}/repositories",
            json={"github_repo_id": 111},
            headers=headers,
        )
        assert dupe.status_code == 409
        unknown = client.post(
            f"/api/projects/{project_id}/repositories",
            json={"github_repo_id": 999},
            headers=headers,
        )
        assert unknown.status_code == 404
        detached = client.delete(
            f"/api/projects/{project_id}/repositories/{first.json()['id']}",
            headers=headers,
        )
        assert detached.status_code == 200
        assert (
            client.delete(
                f"/api/projects/{project_id}/repositories/{first.json()['id']}",
                headers=headers,
            ).status_code
            == 404
        )


def test_install_link_requires_auth_and_valid_id(github_configured, db_session):
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/github/installations", json={"installation_id": 999}
            ).status_code
            == 401
        )
        signup(client, "ameenumhusah@gmail.com")
        headers = headers_for(client, "ameenumhusah@gmail.com")
        assert (
            client.post(
                "/api/github/installations",
                json={"installation_id": 0},
                headers=headers,
            ).status_code
            == 422
        )


def test_reinstall_relinks_to_new_owner(github_configured, db_session):
    from sqlalchemy import select

    from models.github_installation import GitHubInstallation

    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
        signup(client, "ameen.dev09@gmail.com")
        first = headers_for(client, "ameenumhusah@gmail.com")
        second = headers_for(client, "ameen.dev09@gmail.com")
        assert (
            client.post(
                "/api/github/installations",
                json={"installation_id": 4242},
                headers=first,
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/github/installations",
                json={"installation_id": 4242},
                headers=second,
            ).status_code
            == 200
        )
    row = db_session.scalar(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id == 4242
        )
    )
    from models.user import User

    owner = db_session.scalar(
        select(User).where(User.email == "ameen.dev09@gmail.com")
    )
    assert row is not None and row.user_id == owner.id


def test_webhook_intake_filters_and_stores(github_configured, monkeypatch, db_session):
    mock_github_api(monkeypatch)
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
        headers = headers_for(client, "ameen.dev09@gmail.com")
        client.post(
            "/api/github/installations",
            json={"installation_id": 999},
            headers=headers,
        )
        project_id = make_project(
            db_session, user_id_for(db_session, "ameen.dev09@gmail.com")
        )
        attached = client.post(
            f"/api/projects/{project_id}/repositories",
            json={"github_repo_id": 222, "tracked_branch": "main"},
            headers=headers,
        )
        assert attached.status_code == 201

        payload, signature = signed_push("test-secret", 222)
        ok = client.post(
            "/api/github/webhook",
            content=payload,
            headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "push"},
        )
        assert ok.status_code == 200
        assert ok.json()["push_id"]

        payload, _ = signed_push("test-secret", 222)
        tampered = client.post(
            "/api/github/webhook",
            content=payload,
            headers={"X-Hub-Signature-256": "sha256=dead", "X-GitHub-Event": "push"},
        )
        assert tampered.status_code == 401

        payload, signature = signed_push("test-secret", 222, ref="refs/heads/dev")
        wrong_branch = client.post(
            "/api/github/webhook",
            content=payload,
            headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "push"},
        )
        assert wrong_branch.json()["message"] == "Push filtered."

        payload, signature = signed_push("test-secret", 777)
        unknown_repo = client.post(
            "/api/github/webhook",
            content=payload,
            headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "push"},
        )
        assert unknown_repo.json()["message"] == "Repository not connected."

        payload, signature = signed_push("test-secret", 222)
        ping = client.post(
            "/api/github/webhook",
            content=payload,
            headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "ping"},
        )
        assert ping.json()["message"] == "Event ignored."
