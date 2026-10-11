"""Initial schema: users, profiles, projects, repositories, pushes, posts, installs, app settings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("display_name", sa.String(120), nullable=False, default=""),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("bio", sa.Text, nullable=False, default=""),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "owner_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, default=""),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(32),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("github_repo_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, default="other"),
        sa.Column("tracked_branch", sa.String(120), nullable=False, default="main"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_repositories_project_id", "repositories", ["project_id"]
    )
    op.create_table(
        "push_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(32),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column("branch", sa.String(120), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("commit_count", sa.Integer, nullable=False, default=0),
        sa.Column("raw_event", sa.JSON, nullable=True),
        sa.Column("received_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_push_events_repository_id", "push_events", ["repository_id"]
    )
    op.create_table(
        "generated_posts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(32),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.String(32),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column(
            "push_id", sa.String(32), sa.ForeignKey("push_events.id"), nullable=True
        ),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("status", sa.String(32), nullable=False, default="pending"),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_generated_posts_project_id", "generated_posts", ["project_id"]
    )
    op.create_index(
        "ix_generated_posts_repository_id", "generated_posts", ["repository_id"]
    )
    op.create_index(
        "ix_generated_posts_status", "generated_posts", ["status"]
    )
    op.create_table(
        "github_installations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("installation_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("account_login", sa.String(255), nullable=False, default=""),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_github_installations_user_id", "github_installations", ["user_id"]
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    # Seed the admin-tunable repo limit. Change it via the settings
    # service (future admin endpoint), never by editing this file.
    op.execute(
        sa.text(
            "INSERT INTO app_settings (key, value, updated_at) "
            "VALUES ('max_repositories_per_project', '3', CURRENT_TIMESTAMP)"
        )
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("github_installations")
    op.drop_table("generated_posts")
    op.drop_table("push_events")
    op.drop_table("repositories")
    op.drop_table("projects")
    op.drop_table("profiles")
    op.drop_table("users")
