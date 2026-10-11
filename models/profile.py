"""Public profile for a user. One row per user, kept separate from auth."""

from datetime import datetime

from utils.time import utcnow

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.ids import new_id


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(60), unique=True, nullable=True
    )
    headline: Mapped[str] = mapped_column(String(140), default="")
    display_name: Mapped[str] = mapped_column(String(120), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
