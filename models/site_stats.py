"""Site-wide lifetime totals. Exactly one row (`id = 'global'`),
kept in step with user_stats. The admin dashboard reads this one row."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.time import utcnow

GLOBAL_STATS_ID = "global"


class SiteStats(Base):
    __tablename__ = "site_stats"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    total_projects: Mapped[int] = mapped_column(Integer, default=0)
    total_repositories: Mapped[int] = mapped_column(Integer, default=0)
    total_posts_created: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
