"""GitHub App surface: install, repos, webhook. No OAuth user flow."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import settings
from models.github_installation import GitHubInstallation
from models.user import User
from routes.deps import get_current_user, require_github
from schemas.github import AvailableRepository, InstallationLink
from services import github_service
from services.push_service import (
    AI_USE_NOTICE,
    branch_of_ref,
    find_repository_by_github_id,
    record_push_event,
)

router = APIRouter(prefix="/github", tags=["github"])




@router.get("/install-url")
def get_install_url(user: User = Depends(get_current_user)) -> dict:
    require_github()
    if not settings.github_app_slug:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub App slug is not configured.",
        )
    return {"install_url": github_service.install_url()}


@router.post("/installations", status_code=status.HTTP_200_OK)
def link_installation(
    body: InstallationLink,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Claim an installation for the calling user. Re-installs re-link it."""
    row = db.scalar(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id == body.installation_id
        )
    )
    if row is None:
        row = GitHubInstallation(
            installation_id=body.installation_id, user_id=user.id
        )
        db.add(row)
    else:
        row.user_id = user.id
    db.commit()
    return {"message": "GitHub connected.", "installation_id": body.installation_id}




@router.get("/repositories", response_model=list[AvailableRepository])
def list_repositories(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list:
    require_github()
    installation = github_service.user_installation(db, user)
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No GitHub installation connected.",
        )
    try:
        repos = github_service.list_installation_repositories(
            installation.installation_id
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {exc}",
        )
    return [
        {
            "github_repo_id": repo["id"],
            "full_name": repo["full_name"],
            "private": repo.get("private", False),
        }
        for repo in repos
    ]


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    raw = await request.body()
    if not github_service.verify_webhook_signature(
        raw, request.headers.get("X-Hub-Signature-256")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad signature"
        )
    if request.headers.get("X-GitHub-Event", "push") != "push":
        return {"message": "Event ignored."}
    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
        )
    repo = (event.get("repository") or {})
    repository = find_repository_by_github_id(db, repo.get("id", -1))
    if repository is None:
        return {"message": "Repository not connected."}
    commits = event.get("commits") or []
    head = (event.get("head_commit") or {}).get("id", "")
    push = record_push_event(
        db,
        repository,
        branch_of_ref(event.get("ref", "")),
        head,
        commits,
        {"ref": event.get("ref"), "commit_count": len(commits)},
    )
    if push is None:
        return {"message": "Push filtered."}
    return {"message": "Push recorded.", "push_id": push.id}
