from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.support_message import SupportMessage
    from db.models.user import User


class SupportTicket(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('problem', 'idea', 'question', 'message')",
            name="category_allowed",
        ),
        CheckConstraint(
            "status IN ('open', 'waiting_user', 'closed')", name="status_allowed"
        ),
        CheckConstraint(
            "char_length(subject) BETWEEN 5 AND 160", name="subject_length"
        ),
        CheckConstraint(
            "initiated_by IN ('user', 'admin', 'system')",
            name="initiated_by_allowed",
        ),
        UniqueConstraint("owner_id", "welcome_key", name="uq_support_welcome_owner"),
        UniqueConstraint(
            "owner_id",
            "source_announcement_id",
            name="uq_support_announcement_owner",
        ),
        Index("ix_support_tickets_owner_updated_at", "owner_id", "updated_at"),
        Index("ix_support_tickets_status_updated_at", "status", "updated_at"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open", server_default="open"
    )
    initiated_by: Mapped[str] = mapped_column(
        String(16), nullable=False, default="user", server_default="user"
    )
    welcome_key: Mapped[str | None] = mapped_column(String(64))
    source_announcement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("announcements.id", ondelete="SET NULL")
    )
    user_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admin_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="support_tickets")
    messages: Mapped[list[SupportMessage]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupportMessage.created_at",
    )
