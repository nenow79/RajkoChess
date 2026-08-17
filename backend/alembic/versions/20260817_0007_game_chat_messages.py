"""Add persistent chat messages linked to saved games.

Revision ID: 20260817_0007
Revises: 20260815_0006
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0007"
down_revision: str | Sequence[str] | None = "20260815_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fen", sa.String(length=128), nullable=True),
        sa.Column("message_order", sa.SmallInteger(), nullable=False),
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
            "char_length(content) BETWEEN 1 AND 20000",
            name=op.f("ck_chat_messages_content_length"),
        ),
        sa.CheckConstraint(
            "kind IN ('position', 'game_review', 'translation')",
            name=op.f("ck_chat_messages_kind_allowed"),
        ),
        sa.CheckConstraint(
            "message_order BETWEEN 0 AND 10",
            name=op.f("ck_chat_messages_message_order_range"),
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name=op.f("ck_chat_messages_role_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_chat_messages_game_id_games"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_chat_messages_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(
        "ix_chat_messages_game_created_at",
        "chat_messages",
        ["game_id", "created_at"],
    )
    op.create_index(
        "ix_chat_messages_owner_created_at",
        "chat_messages",
        ["owner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_owner_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_game_created_at", table_name="chat_messages")
    op.drop_table("chat_messages")
