from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.common import TimestampMixin, UuidPrimaryKeyMixin
from db.models.enums import SystemRole, UserStatus, enum_values

if TYPE_CHECKING:
    from db.models.analysis import Analysis
    from db.models.auth_session import AuthSession
    from db.models.auth_token import AuthToken
    from db.models.bot import Bot
    from db.models.chat_message import ChatMessage
    from db.models.chess_platform_account import ChessPlatformAccount
    from db.models.game import Game
    from db.models.entitlement import Entitlement
    from db.models.identity import Identity
    from db.models.plan_grant import PlanGrant
    from db.models.payment_order import PaymentOrder
    from db.models.support_ticket import SupportTicket
    from db.models.usage_event import UsageEvent


class User(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_normalized"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    system_role: Mapped[SystemRole] = mapped_column(
        Enum(
            SystemRole,
            name="system_role",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SystemRole.USER,
        server_default=SystemRole.USER.value,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    identities: Mapped[list[Identity]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    auth_tokens: Mapped[list[AuthToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    bots: Mapped[list[Bot]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )
    games: Mapped[list[Game]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )
    chat_messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )
    chess_platform_accounts: Mapped[list[ChessPlatformAccount]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    entitlements: Mapped[list[Entitlement]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    plan_grants: Mapped[list[PlanGrant]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="PlanGrant.user_id",
    )
    payment_orders: Mapped[list[PaymentOrder]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="PaymentOrder.user_id",
    )
    usage_events: Mapped[list[UsageEvent]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    support_tickets: Mapped[list[SupportTicket]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )
