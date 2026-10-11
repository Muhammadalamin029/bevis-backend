"""Profiles and the admin-tunable repo cap."""

from models.profile import Profile
from models.user import User
from services.app_settings import (
    get_max_repositories_per_project,
    set_setting,
)


def test_user_gets_a_separate_profile_row(db_session):
    user = User(email="ameenumhusah@gmail.com", password_hash="hashed")
    db_session.add(user)
    db_session.commit()

    profile = Profile(user_id=user.id, display_name="Ada Pusher")
    db_session.add(profile)
    db_session.commit()

    fetched = db_session.get(Profile, profile.id)
    assert fetched is not None
    assert fetched.user_id == user.id
    assert fetched.display_name == "Ada Pusher"


def test_repo_cap_defaults_to_three(db_session):
    assert get_max_repositories_per_project(db_session) == 3


def test_admin_can_change_repo_cap(db_session):
    set_setting(db_session, "max_repositories_per_project", "5")
    assert get_max_repositories_per_project(db_session) == 5
    set_setting(db_session, "max_repositories_per_project", "3")
    assert get_max_repositories_per_project(db_session) == 3


def test_broken_cap_value_falls_back_to_default(db_session):
    import pytest
    from sqlalchemy import text

    # Writes are validated now; garbage can't arrive through set_setting.
    with pytest.raises(ValueError):
        set_setting(db_session, "max_repositories_per_project", "not-a-number")
    # ...but reads stay defensive against legacy rows written before that.
    db_session.execute(
        text(
            "INSERT INTO app_settings (key, value, updated_at) VALUES "
            "('max_repositories_per_project', 'not-a-number', CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value='not-a-number'"
        )
    )
    assert get_max_repositories_per_project(db_session) == 3
    set_setting(db_session, "max_repositories_per_project", "3")
