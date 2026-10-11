"""Stats helpers. Called by the service functions that create the
underlying rows, in the same transaction, so counters never drift."""

from sqlalchemy.orm import Session

from models.site_stats import GLOBAL_STATS_ID, SiteStats
from models.user_stats import UserStats


def _user_row(db: Session, user_id: str) -> UserStats:
    row = db.get(UserStats, user_id)
    if row is None:
        row = UserStats(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def _site_row(db: Session) -> SiteStats:
    row = db.get(SiteStats, GLOBAL_STATS_ID)
    if row is None:
        row = SiteStats(id=GLOBAL_STATS_ID)
        db.add(row)
        db.flush()
    return row


def record_user_created(db: Session, user_id: str) -> None:
    _user_row(db, user_id)
    site = _site_row(db)
    site.total_users += 1


def record_project_created(db: Session, user_id: str) -> None:
    _user_row(db, user_id).projects_created += 1
    _site_row(db).total_projects += 1


def record_repository_connected(db: Session, user_id: str) -> None:
    _user_row(db, user_id).repositories_connected += 1
    _site_row(db).total_repositories += 1


def record_post_created(db: Session, user_id: str) -> None:
    _user_row(db, user_id).posts_created += 1
    _site_row(db).total_posts_created += 1


def read_site_stats(db: Session) -> dict:
    """Dashboard totals. Lifetime counters plus live breakdowns."""
    from sqlalchemy import func, select

    from models.generated_post import GeneratedPost
    from models.user import User

    site = _site_row(db)
    by_status = dict(
        db.execute(
            select(GeneratedPost.status, func.count()).group_by(
                GeneratedPost.status
            )
        ).all()
    )
    total_users = (
        db.scalar(select(func.count()).select_from(User)) or 0
    )
    verified = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email_verified.is_(True))
        )
        or 0
    )
    return {
        "total_users": site.total_users,
        "total_projects": site.total_projects,
        "total_repositories": site.total_repositories,
        "total_posts_created": site.total_posts_created,
        "verified_email_share": (verified / total_users) if total_users else 0.0,
        "posts_by_status": by_status,
    }
