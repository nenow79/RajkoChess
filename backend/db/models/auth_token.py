from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import UuidPrimaryKeyMixin
from db.models.enums import AuthTokenType, enum_values

if TYPE_CHECKING:
    from db.models.user import User


class AuthToken(UuidPrimaryKeyMixin, Base):
    __tablename__ = "auth_tokens"
    __table_args__ = (
        CheckConstraint("octet_length(token_hash) = 32", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name="consumed_after_creation",
        ),
        Index("ix_auth_tokens_user_id_type", "user_id", "type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[AuthTokenType] = mapped_column(
        Enum(
            AuthTokenType,
            name="auth_token_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    token_hash: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="auth_tokens")
