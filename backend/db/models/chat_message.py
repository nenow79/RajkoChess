from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.game import Game
    from db.models.user import User


class ChatMessage(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role_allowed"),
        CheckConstraint(
            "kind IN ('position', 'game_review', 'translation')",
            name="kind_allowed",
        ),
        CheckConstraint(
            "char_length(content) BETWEEN 1 AND 20000", name="content_length"
        ),
        CheckConstraint(
            "message_order BETWEEN 0 AND 10", name="message_order_range"
        ),
        Index("ix_chat_messages_game_created_at", "game_id", "created_at"),
        Index("ix_chat_messages_owner_created_at", "owner_id", "created_at"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    fen: Mapped[str | None] = mapped_column(String(128))
    message_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    owner: Mapped[User] = relationship(back_populates="chat_messages")
    game: Mapped[Game] = relationship(back_populates="chat_messages")
