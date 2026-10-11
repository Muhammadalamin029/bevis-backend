"""Admin surface. Every route here requires the admin role."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.user import User
from routes.deps import require_admin
from schemas.admin import (
    PlanCreate,
    PlanOut,
    PlanUpdate,
    SettingUpdate,
    StatsOut,
    UserPlanUpdate,
)
from services import (
    EDITABLE_SETTINGS,
    get_setting,
    set_setting,
)
from services.plans import create_plan, list_plans, update_plan
from services.stats import read_site_stats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings")
def read_settings(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> dict:
    return {key: get_setting(db, key, "") for key in sorted(EDITABLE_SETTINGS)}


@router.put("/settings")
def write_setting(
    body: SettingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    if body.key not in EDITABLE_SETTINGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown setting: {body.key}",
        )
    try:
        row = set_setting(db, body.key, body.value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        )
    return {"key": row.key, "value": row.value}


@router.get("/plans", response_model=list[PlanOut])
def read_plans(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list:
    return list_plans(db)


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan_route(
    body: PlanCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        return create_plan(
            db, body.name, body.display_name, body.max_projects,
            body.max_repositories_per_project,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )


@router.put("/plans/{name}", response_model=PlanOut)
def update_plan_route(
    name: str,
    body: PlanUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        return update_plan(
            db,
            name,
            display_name=body.display_name,
            max_projects=body.max_projects,
            max_repositories_per_project=body.max_repositories_per_project,
            is_active=body.is_active,
        )
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if "still has" in message or "already exists" in message
                else status.HTTP_404_NOT_FOUND
            ),
            detail=message,
        )


@router.put("/users/{user_id}/plan", status_code=status.HTTP_200_OK)
def move_user_plan(
    user_id: str,
    body: UserPlanUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    from services.plans import set_user_plan

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    try:
        set_user_plan(db, user, body.plan_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
    return {"id": user.id, "plan_name": user.plan_name}


@router.get("/stats", response_model=StatsOut)
def read_stats(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> dict:
    return read_site_stats(db)
