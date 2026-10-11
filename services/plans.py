"""Plans: resolution and limit checks. Admins edit plan rows;
everyone else reads through these helpers."""

from sqlalchemy.orm import Session

from models.plan import Plan
from models.user import User

FREE_PLAN = "free"


def get_plan(db: Session, name: str) -> Plan | None:
    return db.get(Plan, name)


def plan_for_user(db: Session, user: User) -> Plan:
    """The user's plan, falling back to free if the row ever goes missing."""
    plan = db.get(Plan, user.plan_name)
    if plan is None or not plan.is_active:
        plan = db.get(Plan, FREE_PLAN)
    assert plan is not None, "free plan row missing: migrations not applied?"
    return plan


def set_user_plan(db: Session, user: User, plan_name: str) -> User:
    """Move a user between plans. Admin-only callers (enforced at the route)."""
    plan = db.get(Plan, plan_name)
    if plan is None or not plan.is_active:
        raise ValueError(f"unknown or inactive plan: {plan_name}")
    user.plan_name = plan.name
    db.commit()
    db.refresh(user)
    return user


def list_plans(db: Session) -> list[Plan]:
    from sqlalchemy import select

    return list(db.scalars(select(Plan).order_by(Plan.name)).all())


def create_plan(
    db: Session,
    name: str,
    display_name: str,
    max_projects: int,
    max_repositories_per_project: int,
) -> Plan:
    """Add a plan. Name collisions surface as ValueError."""
    from sqlalchemy import select

    clean = name.strip().lower()
    if not clean:
        raise ValueError("Plan name is required.")
    if db.get(Plan, clean) is not None:
        raise ValueError(f"Plan '{clean}' already exists.")
    plan = Plan(
        name=clean,
        display_name=display_name.strip(),
        max_projects=max_projects,
        max_repositories_per_project=max_repositories_per_project,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(db: Session, name: str, **fields) -> Plan:
    """Patch plan limits. Deactivating a plan people sit on is refused."""
    from sqlalchemy import func, select

    from models.user import User

    plan = db.get(Plan, name)
    if plan is None:
        raise ValueError(f"unknown plan: {name}")
    if fields.get("is_active") is False:
        seated = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.plan_name == name)
            )
            or 0
        )
        if seated > 0:
            raise ValueError(
                f"Plan '{name}' still has {seated} users. Move them first."
            )
    for field, value in fields.items():
        if value is not None and hasattr(plan, field):
            setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    return plan


def user_project_count(db: Session, user_id: str) -> int:
    from sqlalchemy import func, select

    from models.project import Project

    return (
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.owner_id == user_id)
        )
        or 0
    )


def can_create_project(db: Session, user: User) -> tuple[bool, str]:
    """Whether the user's plan has room for one more project."""
    plan = plan_for_user(db, user)
    used = user_project_count(db, user.id)
    if used >= plan.max_projects:
        return False, (
            f"Plan '{plan.display_name}' allows {plan.max_projects} projects."
        )
    return True, ""
