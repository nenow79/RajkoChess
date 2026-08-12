from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.user import User


class Entitlement(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entitlements"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_entitlements_user_key"),
        CheckConstraint(
            "limit_value IS NULL OR limit_value >= 0", name="limit_nonnegative"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    limit_value: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", server_default="manual"
    )

    user: Mapped[User] = relationship(back_populates="entitlements")
