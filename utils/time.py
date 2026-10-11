"""Time helpers. Timestamps are naive UTC everywhere by decision.

SQLite and Postgres both store them without conversion surprises, and every
comparison in the codebase assumes UTC. If timezone-aware datetimes are ever
needed, that change requires a real Alembic migration, not a quiet edit.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
