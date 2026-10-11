"""Email verification and onboarding flags on users."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_verification"
down_revision: str | None = "0003_plans_and_stats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean, nullable=False, default=False),
    )
    op.add_column(
        "users",
        sa.Column("onboarding_completed", sa.Boolean, nullable=False, default=False),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "email_verified")
