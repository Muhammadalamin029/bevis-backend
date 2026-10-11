"""Turnstile CAPTCHA on signup only. HTTP is mocked throughout."""

import httpx
from fastapi.testclient import TestClient

from config.settings import settings
from main import app
from services import captcha


class FakeResponse:
    def __init__(self, payload=None, boom=False):
        self._payload = payload or {}
        self._boom = boom

    def raise_for_status(self):
        if self._boom:
            raise httpx.ConnectError("cloudflare unreachable")

    def json(self):
        return self._payload


def test_off_by_default_without_secret(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    called = []
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: called.append(True) or FakeResponse()
    )
    assert captcha.verify_captcha(None) is True
    assert called == []


def test_success_and_failure_from_cloudflare(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "test-secret")
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: FakeResponse({"success": True})
    )
    assert captcha.verify_captcha("tok") is True
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: FakeResponse({"success": False})
    )
    assert captcha.verify_captcha("tok") is False


def test_network_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "test-secret")
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: FakeResponse(boom=True)
    )
    assert captcha.verify_captcha("tok") is False


def test_missing_token_rejected_when_enforced(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "test-secret")
    assert captcha.verify_captcha(None) is False
    assert captcha.verify_captcha("") is False


def test_signup_enforces_captcha_only_when_configured(monkeypatch):
    with TestClient(app) as client:
        # No secret: no token needed, signup flows.
        monkeypatch.setattr(settings, "turnstile_secret_key", "")
        assert (
            client.post(
                "/api/auth/signup",
                json={"email": "ameenumhusah@gmail.com", "password": "Password123!"},
            ).status_code
            == 201
        )
        # Secret set: missing token dies, valid token passes.
        monkeypatch.setattr(settings, "turnstile_secret_key", "test-secret")
        monkeypatch.setattr(
            httpx, "post", lambda *a, **k: FakeResponse({"success": True})
        )
        assert (
            client.post(
                "/api/auth/signup",
                json={
                    "email": "ameenumhusah+blocked@gmail.com",
                    "password": "Password123!",
                },
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/auth/signup",
                json={
                    "email": "ameen.dev09@gmail.com",
                    "password": "Password123!",
                    "captcha_token": "tok",
                },
            ).status_code
            == 201
        )
