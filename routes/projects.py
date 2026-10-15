"""Project-scoped repository attach/detach. Project CRUD arrives later;
these routes operate on existing, owned projects only."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.database import get_db
from models.project import Project
from models.repository import Repository
from models.user import User
from routes.deps import get_current_user, require_github
from schemas.github import RepositoryAttach, RepositoryAttachOut
from services import github_service
from services.plans import plan_for_user
from services.push_service import AI_USE_NOTICE

router = APIRouter(prefix="/projects", tags=["projects"])


def _owned_project(db: Session, user: User, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.post(
    "/{project_id}/repositories",
    response_model=RepositoryAttachOut,
    status_code=status.HTTP_201_CREATED,
)
def attach_repository(
    project_id: str,
    body: RepositoryAttach,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_github()
    project = _owned_project(db, user, project_id)
    plan = plan_for_user(db, user)
    used = (
        db.scalar(
            select(func.count())
            .select_from(Repository)
            .where(Repository.project_id == project.id)
        )
        or 0
    )
    if used >= plan.max_repositories_per_project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Plan '{plan.display_name}' allows "
                f"{plan.max_repositories_per_project} repositories per project."
            ),
        )
    installation = github_service.user_installation(db, user)
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No GitHub installation connected.",
        )
    try:
        available = {
            repo["id"]: repo
            for repo in github_service.list_installation_repositories(
                installation.installation_id
            )
        }
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {exc}",
        )
    info = available.get(body.github_repo_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not available to this installation.",
        )
    if db.scalar(
        select(Repository).where(
            Repository.github_repo_id == body.github_repo_id
        )
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already connected.",
        )
    repository = Repository(
        project_id=project.id,
        github_repo_id=info["id"],
        full_name=info["full_name"],
        role=body.role,
        tracked_branch=body.tracked_branch,
    )
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return RepositoryAttachOut(
        id=repository.id,
        project_id=repository.project_id,
        github_repo_id=repository.github_repo_id,
        full_name=repository.full_name,
        role=repository.role,
        tracked_branch=repository.tracked_branch,
        notice=AI_USE_NOTICE,
    )


@router.delete(
    "/{project_id}/repositories/{repository_id}",
    status_code=status.HTTP_200_OK,
)
def detach_repository(
    project_id: str,
    repository_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    project = _owned_project(db, user, project_id)
    repository = db.get(Repository, repository_id)
    if repository is None or repository.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )
    db.delete(repository)
    db.commit()
    return {"message": "Repository disconnected."}
