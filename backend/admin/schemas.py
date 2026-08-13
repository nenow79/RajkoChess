import uuid
from datetime import datetime
from typing import Literal

from db.models import SystemRole
from pydantic import BaseModel, Field, field_validator, model_validator


class AdminReason(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Powód musi mieć co najmniej 3 znaki")
        return normalized


class AdminUserUpdate(AdminReason):
    system_role: SystemRole | None = None
    status: Literal["active", "blocked"] | None = None

    @model_validator(mode="after")
    def has_change(self) -> "AdminUserUpdate":
        if self.system_role is None and self.status is None:
            raise ValueError("Podaj rolę lub status do zmiany")
        return self


class EntitlementUpdate(AdminReason):
    enabled: bool
    limit_value: int | None = Field(default=None, ge=0)


class PremiumGrantRequest(AdminReason):
    days: int | None = Field(default=None, ge=1, le=366)
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def has_exactly_one_expiry(self) -> "PremiumGrantRequest":
        if (self.days is None) == (self.ends_at is None):
            raise ValueError("Podaj days albo ends_at")
        return self


class AdminBotInspect(AdminReason):
    pass


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    status: str
    system_role: str
    email_verified: bool
    created_at: str
    plan_key: Literal["free", "premium"] = "free"
    premium_expires_at: str | None = None
