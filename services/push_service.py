"""Push intake: validate, resolve, store. Never generates content here."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.push_event import PushEvent
from models.repository import Repository
from utils.logger import get_logger

logger = get_logger("push")

AI_USE_NOTICE = (
    "Code changes from this repository will be sent to an AI model "
    "to generate posts."
)


def find_repository_by_github_id(db: Session, github_repo_id: int) -> Repository | None:
    return db.scalar(
        select(Repository).where(Repository.github_repo_id == github_repo_id)
    )


def branch_of_ref(ref: str) -> str:
    """refs/heads/main -> main. Anything else passes through untouched."""
    prefix = "refs/heads/"
    return ref[len(prefix):] if ref.startswith(prefix) else ref


def record_push_event(
    db: Session,
    repository: Repository,
    branch: str,
    head_sha: str,
    commits: list,
    raw_event: dict,
) -> PushEvent | None:
    """Store qualifying pushes. Returns None for filtered-out events."""
    if branch != repository.tracked_branch:
        logger.info(
            "ignoring push to untracked branch %s on %s",
            branch,
            repository.full_name,
        )
        return None
    push = PushEvent(
        repository_id=repository.id,
        branch=branch,
        head_sha=head_sha,
        commit_count=len(commits),
        raw_event=raw_event,
    )
    db.add(push)
    db.commit()
    db.refresh(push)
    return push
