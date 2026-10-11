"""Plans. Admin-editable limits; `free` is seeded by migration."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.time import utcnow


class Plan(Base):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    max_projects: Mapped[int] = mapped_column(Integer, default=3)
    max_repositories_per_project: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
