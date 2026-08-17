from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin
from db.models.enums import GameSource, enum_values

if TYPE_CHECKING:
    from db.models.analysis import Analysis
    from db.models.chat_message import ChatMessage
    from db.models.user import User


class Game(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("char_length(pgn) BETWEEN 1 AND 2000000", name="pgn_length"),
        UniqueConstraint(
            "owner_id", "source", "external_id", name="uq_games_owner_source_external"
        ),
        Index("ix_games_owner_played_at", "owner_id", "played_at"),
        Index("ix_games_owner_created_at", "owner_id", "created_at"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[GameSource] = mapped_column(
        Enum(
            GameSource,
            name="game_source",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GameSource.PGN,
    )
    external_id: Mapped[str | None] = mapped_column(String(128))
    pgn: Mapped[str] = mapped_column(Text, nullable=False)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )

    owner: Mapped[User] = relationship(back_populates="games")
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="game", cascade="all, delete-orphan", passive_deletes=True
    )
    chat_messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="game", cascade="all, delete-orphan", passive_deletes=True
    )
