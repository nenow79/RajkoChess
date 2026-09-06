from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.support_ticket import SupportTicket
    from db.models.user import User


class SupportMessage(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "support_messages"
    __table_args__ = (
        CheckConstraint("author_role IN ('user', 'admin')", name="author_role_allowed"),
        CheckConstraint(
            "char_length(content) BETWEEN 1 AND 5000", name="content_length"
        ),
        Index("ix_support_messages_ticket_created_at", "ticket_id", "created_at"),
        Index("ix_support_messages_author_created_at", "author_id", "created_at"),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    author_role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped[SupportTicket] = relationship(back_populates="messages")
    author: Mapped[User | None] = relationship()
