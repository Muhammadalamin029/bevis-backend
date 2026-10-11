"""Profile rules. Usernames are unique, lowercase, URL-friendly."""

import re
from sqlalchemy.orm import Session

from models.profile import Profile

USERNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,58}[a-z0-9])?$")


def normalize_username(raw: str) -> str:
    """Trim and lowercase. Raises ValueError when the shape is illegal."""
    username = raw.strip().lower()
    if not USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 1-60 chars: lowercase letters, digits, "
            "dots, dashes, underscores. Must start and end alphanumerically."
        )
    return username


def set_username(db: Session, user_id: str, raw: str) -> Profile:
    """Claim or change a username. 409-style conflict surfaces as ValueError."""
    from sqlalchemy import select

    username = normalize_username(raw)
    taken = db.scalar(
        select(Profile).where(
            Profile.username == username, Profile.user_id != user_id
        )
    )
    if taken is not None:
        raise ValueError(f"Username '{username}' is already taken.")
    profile = get_profile(db, user_id)
    if profile is None:
        raise ValueError("No profile for user.")
    profile.username = username
    db.commit()
    db.refresh(profile)
    return profile


def get_profile(db: Session, user_id: str) -> Profile | None:
    from sqlalchemy import select

    return db.scalar(select(Profile).where(Profile.user_id == user_id))


def update_profile(
    db: Session,
    user_id: str,
    *,
    display_name: str | None = None,
    bio: str | None = None,
    avatar_url: str | None = None,
    headline: str | None = None,
    username: str | None = None,
) -> Profile:
    """Patch profile fields. Username goes through claim validation."""
    from sqlalchemy import select

    profile = get_profile(db, user_id)
    if profile is None:
        raise ValueError("No profile for user.")
    if username is not None:
        candidate = normalize_username(username)
        taken = db.scalar(
            select(Profile).where(
                Profile.username == candidate, Profile.user_id != user_id
            )
        )
        if taken is not None:
            raise ValueError(f"Username '{candidate}' is already taken.")
        profile.username = candidate
    if display_name is not None:
        profile.display_name = display_name.strip()
    if bio is not None:
        profile.bio = bio
    if avatar_url is not None:
        profile.avatar_url = avatar_url
    if headline is not None:
        profile.headline = headline.strip()
    db.commit()
    db.refresh(profile)
    return profile
