import uuid
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
