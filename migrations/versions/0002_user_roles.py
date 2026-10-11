"""User roles for RBAC. Existing rows become customers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_roles"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="customer"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
