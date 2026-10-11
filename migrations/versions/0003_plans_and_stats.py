"""Plans, profile fields, stats tables, and the free-plan seed."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_plans_and_stats"
down_revision: str | None = "0002_user_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("name", sa.String(60), primary_key=True),
        sa.Column("display_name", sa.String(120), nullable=False, default=""),
        sa.Column("max_projects", sa.Integer, nullable=False, default=3),
        sa.Column(
            "max_repositories_per_project", sa.Integer, nullable=False, default=3
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO plans (name, display_name, max_projects, "
            "max_repositories_per_project, is_active, created_at, updated_at) "
            "VALUES ('free', 'Free', 3, 3, TRUE, CURRENT_TIMESTAMP, "
            "CURRENT_TIMESTAMP)"
        )
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "plan_name",
                sa.String(120),
                nullable=False,
                server_default="free",
            )
        )
        batch_op.create_foreign_key(
            "fk_users_plan_name", "plans", ["plan_name"], ["name"]
        )
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(60), nullable=True))
        batch_op.create_unique_constraint("uq_profiles_username", ["username"])
        batch_op.add_column(
            sa.Column(
                "headline", sa.String(140), nullable=False, server_default=""
            )
        )
    op.create_table(
        "user_stats",
        sa.Column(
            "user_id", sa.String(32), sa.ForeignKey("users.id"), primary_key=True
        ),
        sa.Column("projects_created", sa.Integer, nullable=False, default=0),
        sa.Column("repositories_connected", sa.Integer, nullable=False, default=0),
        sa.Column("posts_created", sa.Integer, nullable=False, default=0),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "site_stats",
        sa.Column("id", sa.String(60), primary_key=True),
        sa.Column("total_users", sa.Integer, nullable=False, default=0),
        sa.Column("total_projects", sa.Integer, nullable=False, default=0),
        sa.Column("total_repositories", sa.Integer, nullable=False, default=0),
        sa.Column("total_posts_created", sa.Integer, nullable=False, default=0),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO site_stats (id, total_users, total_projects, "
            "total_repositories, total_posts_created, updated_at) VALUES "
            "('global', 0, 0, 0, 0, CURRENT_TIMESTAMP)"
        )
    )


def downgrade() -> None:
    op.drop_table("site_stats")
    op.drop_table("user_stats")
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_column("headline")
        batch_op.drop_column("username")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("plan_name")
    op.drop_table("plans")
