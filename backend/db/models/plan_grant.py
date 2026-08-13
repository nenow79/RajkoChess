from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.user import User


class PlanGrant(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plan_grants"
    __table_args__ = (
        CheckConstraint("plan_key = 'premium'", name="supported_plan"),
        CheckConstraint("ends_at > starts_at", name="ends_after_start"),
        Index("ix_plan_grants_user_period", "user_id", "starts_at", "ends_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="premium", server_default="premium"
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", server_default="manual"
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship(
        back_populates="plan_grants", foreign_keys=[user_id]
    )
    granted_by: Mapped[User | None] = relationship(foreign_keys=[granted_by_user_id])
