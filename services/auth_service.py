"""Password hashing, JWT tokens, user lifecycle. No route logic here."""

from datetime import timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import settings
from models.profile import Profile
from models.user import ROLE_ADMIN, ROLE_CUSTOMER, User
from services import token_store
from utils.logger import get_logger
from utils.time import utcnow

logger = get_logger("auth")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def check_password_strength(password: str) -> str | None:
    """One password rule for every entry point. None means strong enough."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in password):
        return "Password must include an uppercase letter."
    if not any(c.islower() for c in password):
        return "Password must include a lowercase letter."
    if all(c.isalnum() for c in password):
        return "Password must include a special character."
    return None


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower().strip()))


def create_user(
    db: Session, email: str, password: str, role: str = ROLE_CUSTOMER
) -> User:
    """Create a user plus their profile row. Caller checks duplicates first."""
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id))
    from services.stats import record_user_created

    record_user_created(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user: User) -> str:
    expires = utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": user.id, "role": user.role, "exp": expires},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None


def ensure_admin_from_env(db: Session) -> User | None:
    """Seed the first admin idempotently. Empty env means skip silently."""
    email = settings.admin_email.strip().lower()
    if not email or not settings.admin_password:
        return None
    existing = get_user_by_email(db, email)
    if existing is not None:
        return existing
    return create_user(db, email, settings.admin_password, role=ROLE_ADMIN)


def issue_token_pair(user: User) -> dict:
    """One access token plus one refresh token. Refresh is shown once."""
    return {
        "access_token": create_access_token(user),
        "refresh_token": token_store.issue(user.id),
        "token_type": "bearer",
    }


def rotate_refresh_token(db: Session, refresh_token: str) -> dict | None:
    """Burn the presented refresh token, issue a fresh pair. None if dead."""
    user_id = token_store.lookup(refresh_token)
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        return None
    token_store.revoke(refresh_token)
    return issue_token_pair(user)


def request_password_reset(db: Session, email: str) -> str | None:
    """Create a reset token, or None for unknown emails (callers say nothing).

    Delivery goes through the email queue. With no mailer configured the
    worker logs and drops it; the raw token never leaves this return value,
    which exists so tests (and only tests) can complete the flow.
    """
    from services.email import queue_password_reset_email

    user = get_user_by_email(db, email)
    if user is None:
        return None
    token = token_store.issue_reset(user.id)
    queue_password_reset_email(user.email, token)
    return token


def reset_password(db: Session, token: str, new_password: str) -> bool:
    """Consume a reset token and set the password. Burns every session."""
    user_id = token_store.consume_reset(token)
    if user_id is None:
        return False
    user = db.get(User, user_id)
    if user is None:
        return False
    user.password_hash = hash_password(new_password)
    db.commit()
    token_store.revoke_all_for_user(user.id)
    return True


def change_password(db: Session, user: User, current: str, new: str) -> bool:
    """Change with proof of the old password. Burns every session."""
    if not verify_password(current, user.password_hash):
        return False
    user.password_hash = hash_password(new)
    db.commit()
    token_store.revoke_all_for_user(user.id)
    return True
