from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin
from db.models.enums import AnalysisStatus, enum_values

if TYPE_CHECKING:
    from db.models.game import Game
    from db.models.user import User


class Analysis(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_owner_created_at", "owner_id", "created_at"),
        Index("ix_analyses_game_created_at", "game_id", "created_at"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(
            AnalysisStatus,
            name="analysis_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=AnalysisStatus.COMPLETED,
    )
    engine_result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    coach_response: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="analyses")
    game: Mapped[Game] = relationship(back_populates="analyses")
