"""Own profile, onboarding, and self-deletion."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.user import User
from routes.deps import get_current_user
from schemas.user import DeleteConfirm, DeleteRequest, OnboardingIn, PublicProfile, UpdateProfile
from services import profiles
from services.auth_service import verify_password
from services.email import queue_deletion_email
from services.users import delete_user
from services.verification import PURPOSE_DELETE, check_code, issue_code

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=PublicProfile)
def read_own_profile(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    profile = profiles.get_profile(db, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        )
    return profile


@router.patch("/me", response_model=PublicProfile)
def update_own_profile(
    body: UpdateProfile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return profiles.update_profile(
            db,
            user.id,
            display_name=body.display_name,
            bio=body.bio,
            avatar_url=body.avatar_url,
            headline=body.headline,
            username=body.username,
        )
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if "already taken" in message
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=message,
        )


@router.post("/delete/request", status_code=status.HTTP_200_OK)
def request_account_deletion(
    body: DeleteRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Step 1: prove the password, receive an OTP. Nothing is deleted yet."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    code = issue_code(user.id, purpose=PURPOSE_DELETE)
    queue_deletion_email(user.email, code)
    return {"message": "Deletion code sent. Check your email."}


@router.post("/delete/confirm", status_code=status.HTTP_200_OK)
def confirm_account_deletion(
    body: DeleteConfirm,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Step 2: a valid code wipes the account. Password already proven."""
    if not check_code(user.id, body.code, purpose=PURPOSE_DELETE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code",
        )
    delete_user(db, user, None)
    return {"message": "Account deleted."}


@router.post("/onboarding", status_code=status.HTTP_200_OK)
def complete_onboarding(
    body: OnboardingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if user.onboarding_completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onboarding already completed",
        )
    try:
        profiles.update_profile(
            db, user.id, username=body.username, headline=body.headline
        )
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if "already taken" in message
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=message,
        )
    user.onboarding_completed = True
    db.commit()
    return {"message": "Onboarding complete. Welcome in."}
