"""Auth request/response shapes. Passwords never leave the request body."""

from pydantic import BaseModel, EmailStr, Field


class CreateUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Cloudflare Turnstile token from the signup form. Required only
    # when a Turnstile secret is configured; the FE owns this field.
    captcha_token: str | None = None


class AuthenticateUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPair(AccessToken):
    refresh_token: str


class RefreshToken(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutIn(BaseModel):
    # Best-effort: absent or dead tokens still return 200, because the
    # end state the user wants (logged out locally) already holds.
    refresh_token: str | None = None


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PublicUser(BaseModel):
    id: str
    email: str
    role: str
    plan_name: str
    email_verified: bool
    onboarding_completed: bool

    model_config = {"from_attributes": True}


class PublicProfile(BaseModel):
    username: str | None
    display_name: str
    headline: str
    avatar_url: str | None
    bio: str

    model_config = {"from_attributes": True}


class UpdateProfile(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=1024)
    headline: str | None = Field(default=None, max_length=140)
    username: str | None = Field(default=None, max_length=60)


class OnboardingIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    headline: str = Field(min_length=1, max_length=140)
    display_name: str | None = Field(default=None, max_length=120)


class DeleteRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class DeleteConfirm(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class VerifyEmailIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)
