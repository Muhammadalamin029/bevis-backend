"""Admin-tunable settings. The repo cap lives in the DB, not in code."""

from sqlalchemy.orm import Session

from models.app_setting import AppSetting

MAX_REPOSITORIES_KEY = "max_repositories_per_project"
DEFAULT_MAX_REPOSITORIES = 3

# The only app_settings keys the admin API may write. Everything else
# is read-only so a typo can't invent live configuration.
EDITABLE_SETTINGS = frozenset({MAX_REPOSITORIES_KEY})


def get_setting(db: Session, key: str, default: str) -> str:
    """Read a setting, falling back when the row is missing."""
    row = db.get(AppSetting, key)
    return row.value if row is not None else default


def set_setting(db: Session, key: str, value: str) -> AppSetting:
    """Create or update a setting. Admin-only callers (enforced at the route)."""
    if key == MAX_REPOSITORIES_KEY:
        try:
            parsed = int(value)
        except ValueError:
            raise ValueError(f"{key} must be an integer.")
        if parsed < 1:
            raise ValueError(f"{key} must be at least 1.")
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    db.refresh(row)
    return row


def get_max_repositories_per_project(db: Session) -> int:
    """The per-project repo cap. Change it with set_setting, never in code."""
    raw = get_setting(db, MAX_REPOSITORIES_KEY, str(DEFAULT_MAX_REPOSITORIES))
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_REPOSITORIES
