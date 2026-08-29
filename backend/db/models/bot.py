from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin
from db.models.enums import BotVisibility, enum_values

if TYPE_CHECKING:
    from db.models.user import User


class Bot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bots"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint(
            "char_length(description) BETWEEN 1 AND 1000", name="description_length"
        ),
        CheckConstraint("target_elo BETWEEN 800 AND 2800", name="target_elo_range"),
        CheckConstraint(
            "(visibility = 'public' AND owner_id IS NULL) OR "
            "(visibility = 'private' AND owner_id IS NOT NULL)",
            name="visibility_owner",
        ),
        Index("ix_bots_visibility_created_at", "visibility", "created_at"),
        Index("ix_bots_owner_id_created_at", "owner_id", "created_at"),
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    visibility: Mapped[BotVisibility] = mapped_column(
        Enum(
            BotVisibility,
            name="bot_visibility",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=BotVisibility.PRIVATE,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    avatar: Mapped[str] = mapped_column(String(32), nullable=False, default="🤖")
    target_elo: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_weakening: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    style: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    openings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    phrases: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)

    owner: Mapped[User | None] = relationship(back_populates="bots")
