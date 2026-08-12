from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from db.models.user import User


class Identity(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_subject", name="uq_identities_provider_subject"
        ),
        UniqueConstraint("user_id", "provider", name="uq_identities_user_provider"),
        CheckConstraint(
            "(provider = 'password' AND password_hash IS NOT NULL) OR "
            "(provider <> 'password' AND password_hash IS NULL)",
            name="password_hash_matches_provider",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="identities")
