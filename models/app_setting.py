"""Admin-tunable application settings. Code reads, admins write."""

from datetime import datetime

from utils.time import utcnow

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
