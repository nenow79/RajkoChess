from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.user import User


class ChessPlatformAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chess_platform_accounts"
    __table_args__ = (
        CheckConstraint("provider = lower(provider)", name="provider_normalized"),
        CheckConstraint(
            "char_length(username) BETWEEN 1 AND 80", name="username_length"
        ),
        CheckConstraint(
            "char_length(normalized_username) BETWEEN 1 AND 80",
            name="normalized_username_length",
        ),
        UniqueConstraint(
            "user_id", "provider", name="uq_chess_platform_accounts_user_provider"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_username: Mapped[str] = mapped_column(String(80), nullable=False)

    user: Mapped[User] = relationship(back_populates="chess_platform_accounts")
