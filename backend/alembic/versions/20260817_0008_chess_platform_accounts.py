"""Add default usernames for external chess platforms.

Revision ID: 20260817_0008
Revises: 20260817_0007
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0008"
down_revision: str | Sequence[str] | None = "20260817_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chess_platform_accounts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("normalized_username", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(normalized_username) BETWEEN 1 AND 80",
            name=op.f("ck_chess_platform_accounts_normalized_username_length"),
        ),
        sa.CheckConstraint(
            "provider = lower(provider)",
            name=op.f("ck_chess_platform_accounts_provider_normalized"),
        ),
        sa.CheckConstraint(
            "char_length(username) BETWEEN 1 AND 80",
            name=op.f("ck_chess_platform_accounts_username_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chess_platform_accounts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chess_platform_accounts")),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_chess_platform_accounts_user_provider",
        ),
    )


def downgrade() -> None:
    op.drop_table("chess_platform_accounts")
