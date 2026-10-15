"""Signup, signin, me. Customers self-serve; admins are seeded, never signed up."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.user import ROLE_ADMIN, User
from routes.deps import get_current_user
from schemas.user import VerifyEmailIn
from services import verification
from services.email import queue_verification_email
from schemas.user import (
    ChangePassword,
    ForgotPassword,
    LogoutIn,
    RefreshToken,
    ResetPassword,
    AuthenticateUser,
    CreateUser,
    AccessToken,
    TokenPair,
    PublicUser,
)
from services.auth_service import (
    authenticate,
    change_password,
    check_password_strength,
    create_user,
    get_user_by_email,
    issue_token_pair,
    request_password_reset,
    reset_password,
    rotate_refresh_token,
)
from services.captcha import verify_captcha
from services.email import queue_welcome_email
from services.rate_limit import (
    LOCKOUT_WINDOW_SECONDS,
    clear_failed_logins,
    is_locked_out,
    record_failed_login,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
def signup(body: CreateUser, db: Session = Depends(get_db)) -> User:
    if get_user_by_email(db, body.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    weak = check_password_strength(body.password)
    if weak is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=weak
        )
    if not verify_captcha(body.captcha_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed",
        )
    user = create_user(db, body.email, body.password)
    queue_welcome_email(user.email)
    return user


@router.post("/signin", response_model=TokenPair)
def signin(body: AuthenticateUser, db: Session = Depends(get_db)) -> dict:
    if is_locked_out(body.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(LOCKOUT_WINDOW_SECONDS)},
        )
    user = authenticate(db, body.email, body.password)
    if user is None:
        record_failed_login(body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    clear_failed_logins(body.email)
    return issue_token_pair(user)


@router.get("/me", response_model=PublicUser)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshToken, db: Session = Depends(get_db)) -> dict:
    pair = rotate_refresh_token(db, body.refresh_token)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return pair


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(body: LogoutIn) -> dict:
    from services import token_store

    if body.refresh_token:
        token_store.revoke(body.refresh_token)
    return {"message": "Signed out."}


@router.post("/logout-all", status_code=status.HTTP_200_OK)
def logout_all(user: User = Depends(get_current_user)) -> dict:
    from services import token_store

    token_store.revoke_all_for_user(user.id)
    return {"message": "Signed out everywhere."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(body: ForgotPassword, db: Session = Depends(get_db)) -> dict:
    # Always 200: the response must not reveal whether the email exists.
    request_password_reset(db, body.email)
    return {"message": "If that email is registered, a reset link is on its way."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password_route(body: ResetPassword, db: Session = Depends(get_db)) -> dict:
    weak = check_password_strength(body.new_password)
    if weak is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=weak
        )
    if not reset_password(db, body.token, body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    return {"message": "Password updated. Sign in again."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password_route(
    body: ChangePassword,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    weak = check_password_strength(body.new_password)
    if weak is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=weak
        )
    if not change_password(db, user, body.current_password, body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    return {"message": "Password updated. Sign in again on other devices."}


@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(
    body: VerifyEmailIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if user.email_verified:
        return {"message": "Email already verified."}
    if not verification.check_code(user.id, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code",
        )
    user.email_verified = True
    db.commit()
    return {"message": "Email verified."}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
def resend_verification(user: User = Depends(get_current_user)) -> dict:
    if user.email_verified:
        return {"message": "Email already verified."}
    if verification.on_cooldown(user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A code was just sent. Wait a minute.",
            headers={
                "Retry-After": str(verification.cooldown_seconds_left(user.id))
            },
        )
    code = verification.issue_code(user.id)
    queue_verification_email(user.email, code)
    return {"message": "Verification code sent."}
