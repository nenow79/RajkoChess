import uuid
from datetime import datetime

from db.models import SystemRole, User, UserStatus
from pydantic import BaseModel, EmailStr, Field, field_validator

from auth.security import validate_password_strength


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("password")
    @classmethod
    def password_is_strong_enough(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class EmailVerificationResendRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str

    @field_validator("password")
    @classmethod
    def password_is_strong_enough(cls, value: str) -> str:
        return validate_password_strength(value)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    status: UserStatus
    system_role: SystemRole
    email_verified: bool
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            system_role=user.system_role,
            email_verified=user.email_verified_at is not None,
            created_at=user.created_at,
        )


class LoginResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class CsrfResponse(BaseModel):
    csrf_token: str


class LogoutResponse(BaseModel):
    logged_out: bool = True
    revoked_sessions: int = 1


class MessageResponse(BaseModel):
    message: str
