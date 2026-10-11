"""User lifecycle beyond auth: full self-delete with cascade."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.generated_post import GeneratedPost
from models.github_installation import GitHubInstallation
from models.profile import Profile
from models.project import Project
from models.push_event import PushEvent
from models.repository import Repository
from models.user import User
from models.user_stats import UserStats
from services import token_store
from services.auth_service import verify_password


def delete_user(db: Session, user: User, current_password: str | None = None) -> bool:
    """Wipe everything the user owns. No orphans.

    Pass the current password and it is verified first (single-step
    callers). Pass None when a previous step already proved identity,
    such as the delete-confirm OTP (staged callers).

    Order respects foreign keys, children before parents. Refresh
    sessions burn, stats rows go with the user, the global site row
    only decrements its user count.
    """
    if current_password is not None and not verify_password(
        current_password, user.password_hash
    ):
        return False

    project_ids = db.scalars(
        select(Project.id).where(Project.owner_id == user.id)
    ).all()
    if project_ids:
        repo_ids = db.scalars(
            select(Repository.id).where(Repository.project_id.in_(project_ids))
        ).all()
        if repo_ids:
            db.execute(
                delete(GeneratedPost).where(
                    GeneratedPost.repository_id.in_(repo_ids)
                )
            )
            db.execute(
                delete(PushEvent).where(PushEvent.repository_id.in_(repo_ids))
            )
            db.execute(
                delete(Repository).where(Repository.id.in_(repo_ids))
            )
        db.execute(delete(Project).where(Project.id.in_(project_ids)))
    db.execute(delete(GitHubInstallation).where(GitHubInstallation.user_id == user.id))
    db.execute(delete(Profile).where(Profile.user_id == user.id))
    db.execute(delete(UserStats).where(UserStats.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()

    token_store.revoke_all_for_user(user.id)
    from models.site_stats import GLOBAL_STATS_ID, SiteStats

    site = db.get(SiteStats, GLOBAL_STATS_ID)
    if site is not None and site.total_users > 0:
        site.total_users -= 1
        db.commit()
    return True
