from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.plan_grant import PlanGrant
    from db.models.user import User


class PaymentOrder(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="amount_positive"),
        CheckConstraint("premium_days BETWEEN 1 AND 366", name="premium_days_range"),
        CheckConstraint("currency = 'PLN'", name="currency_pln"),
        CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')", name="status_allowed"
        ),
        Index("ix_payment_orders_status_created_at", "status", "created_at"),
        Index(
            "uq_payment_orders_one_pending_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reference_code: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="PLN", server_default="PLN"
    )
    premium_days: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient: Mapped[str] = mapped_column(String(160), nullable=False)
    iban: Mapped[str] = mapped_column(String(34), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    plan_grant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plan_grants.id", ondelete="SET NULL"), unique=True
    )
    admin_note: Mapped[str | None] = mapped_column(String(1000))

    user: Mapped[User] = relationship(
        back_populates="payment_orders", foreign_keys=[user_id]
    )
    plan_grant: Mapped[PlanGrant | None] = relationship()
