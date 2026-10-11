"""Email through Celery: delivery, retries, and enqueue points."""

import httpx
from fastapi.testclient import TestClient

from main import app
from services import email_tasks


def signup(client: TestClient, email: str, password: str = "Password123!") -> dict:
    response = client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_signup_enqueues_welcome_email(monkeypatch):
    from services import email as email_service

    sent = []
    monkeypatch.setattr(
        email_tasks, "_post_to_sendlib", lambda to, subject, html: sent.append(to)
    )
    with TestClient(app) as client:
        signup(client, "ameenumhusah@gmail.com")
    assert sent == ["ameenumhusah@gmail.com"]


def test_reset_email_carries_token_link(monkeypatch, db_session):
    from services.auth_service import request_password_reset

    bodies = []
    monkeypatch.setattr(
        email_tasks,
        "_post_to_sendlib",
        lambda to, subject, html: bodies.append(html),
    )
    with TestClient(app) as client:
        signup(client, "ameen.dev09@gmail.com")
    token = request_password_reset(db_session, "ameen.dev09@gmail.com")
    assert token is not None
    # Welcome (from signup) plus the reset the service enqueued itself.
    assert len(bodies) == 2
    reset_body = bodies[1]
    assert token in reset_body
    assert "/reset-password?token=" in reset_body


def test_persistent_sendlib_failure_drops_after_retries(monkeypatch):
    failures = []

    def always_down(to, subject, html):
        failures.append(to)
        raise httpx.ConnectError("sendlib unreachable")

    monkeypatch.setattr(email_tasks, "_post_to_sendlib", always_down)
    with TestClient(app) as client:
        # Signup still succeeds: mail never blocks the request path.
        signup(client, "ameenumhusah@gmail.com")
    # Initial attempt plus the bounded retries, then the drop is logged.
    assert failures == ["ameenumhusah@gmail.com"] * 6


def test_unknown_template_fails_fast_without_retry():
    from services.email_tasks import send_email

    try:
        send_email.run(to="ameen.dev09@gmail.com", template="nope", context={})
        raised = False
    except ValueError:
        raised = True
    assert raised
