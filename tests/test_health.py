"""Milestone 1: the app boots, tables exist, health reports connected."""

from fastapi.testclient import TestClient

from main import app


def test_root_answers():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Bevis" in response.json()["message"]


def test_health_reports_connected_database():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_all_prd_tables_exist():
    from sqlalchemy import inspect

    from config.database import engine

    with TestClient(app):
        tables = sorted(inspect(engine).get_table_names())
    for expected in (
        "users",
        "profiles",
        "projects",
        "repositories",
        "push_events",
        "generated_posts",
        "github_installations",
        "app_settings",
    ):
        assert expected in tables
