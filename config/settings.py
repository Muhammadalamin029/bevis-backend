"""Application settings. Every value overridable via BEVIS_* env vars."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BEVIS_", env_file=".env", extra="ignore"
    )

    app_name: str = "Bevis"
    app_description: str = (
        "Don't say it. Show proof. "
        "Turns GitHub pushes into ready-to-post developer content."
    )
    environment: str = "development"
    # SQLite by default for local dev. Point at Postgres in production,
    # e.g. postgresql+psycopg://user:pass@host:5432/bevis
    database_url: str = "sqlite:///./bevis.db"
    api_prefix: str = "/api"

    # Auth. Override the secret in every real deployment.
    jwt_secret_key: str = "dev-secret-change-me-to-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    reset_token_expire_minutes: int = 60

    # Sessions live in Redis. Sessions are ephemeral: a Redis restart
    # logs everyone out rather than corrupting anything.
    redis_url: str = "redis://localhost:6379/0"

    # Celery rides the same Redis. Separate settings so the broker can
    # move without touching session storage.
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # Email goes out only through Celery tasks, never inline.
    sendlib_api_url: str = "https://sendlib.samueltuoyo.com/api/send"
    # Turnstile CAPTCHA, signup route only. Empty secret = verification off.
    turnstile_verify_url: str = (
        "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    )
    turnstile_secret_key: str = ""
    sendlib_api_key: str = ""
    sendlib_from: str = ""
    frontend_url: str = "http://localhost:5173"
    email_max_retries: int = 5

    # First admin, seeded idempotently on boot. Empty means skip seeding.
    admin_email: str = ""
    admin_password: str = ""

    # GitHub App. Empty means GitHub features refuse cleanly (503).
    github_app_id: str = ""
    github_app_slug: str = ""
    github_private_key: str = ""
    github_private_key_file: str = ""
    github_webhook_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    github_api_url: str = "https://api.github.com"


settings = Settings()
