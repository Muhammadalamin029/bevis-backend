"""A stored GitHub push event. Generation reads from this, never re-fetches."""

from datetime import datetime

from utils.time import utcnow

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.ids import new_id


class PushEvent(Base):
    __tablename__ = "push_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id"), index=True
    )
    branch: Mapped[str] = mapped_column(String(120))
    head_sha: Mapped[str] = mapped_column(String(64))
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_event: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
