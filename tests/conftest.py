"""Test setup. One throwaway SQLite file, migrated with real Alembic."""

import os

TEST_DB_FILE = "test_bevis.db"
os.environ["BEVIS_DATABASE_URL"] = f"sqlite:///./{TEST_DB_FILE}"
# Pin auth behavior: a developer .env must never change test outcomes.
os.environ["BEVIS_ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
# Tests must never send real mail, even with a real key configured locally.
os.environ["BEVIS_SENDLIB_API_KEY"] = ""
# Tests must never depend on a real Turnstile secret either.
os.environ["BEVIS_TURNSTILE_SECRET_KEY"] = ""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    cfg = Config("alembic.ini")
    cfg.set_main_option(
        "sqlalchemy.url", os.environ["BEVIS_DATABASE_URL"]
    )
    command.upgrade(cfg, "head")
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


@pytest.fixture()
def db_session():
    engine = create_engine(os.environ["BEVIS_DATABASE_URL"])
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """All token storage hits a fake. Real Redis is a deploy concern."""
    import fakeredis

    from services import token_store

    fake = fakeredis.FakeRedis(decode_responses=True)
    # Single seam: every module reaches Redis through config.redis.
    monkeypatch.setattr("config.redis.get_redis_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def eager_celery():
    """Tasks execute inline. No broker needed for the suite."""
    from services.queue import celery_app

    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False


@pytest.fixture(autouse=True)
def clean_database():
    """Wipe every table after each test so tests never see each other."""
    yield
    engine = create_engine(os.environ["BEVIS_DATABASE_URL"])
    with engine.begin() as connection:
        # Reverse metadata order = children before parents. New tables
        # are covered automatically; never hand-list them here.
        from config.database import Base

        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "alembic_version":
                continue
            connection.execute(text(f"DELETE FROM {table.name}"))
        connection.execute(
            text(
                "INSERT INTO app_settings (key, value, updated_at) VALUES "
                "('max_repositories_per_project', '3', CURRENT_TIMESTAMP)"
            )
        )
        # Re-seed migration seeds the wipe removes (plans.free).
        connection.execute(
            text(
                "INSERT INTO plans (name, display_name, max_projects, "
                "max_repositories_per_project, is_active, created_at, "
                "updated_at) VALUES ('free', 'Free', 3, 3, TRUE, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()
