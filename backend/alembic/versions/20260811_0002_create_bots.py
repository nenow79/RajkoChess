"""Create PostgreSQL bot catalog with ownership and visibility.

Revision ID: 20260811_0002
Revises: 20260811_0001
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0002"
down_revision: str | Sequence[str] | None = "20260811_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

bot_visibility_enum = postgresql.ENUM(
    "public", "private", name="bot_visibility", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    bot_visibility_enum.create(bind, checkfirst=True)

    op.create_table(
        "bots",
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("visibility", bot_visibility_enum, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("avatar", sa.String(length=32), nullable=False),
        sa.Column("target_elo", sa.Integer(), nullable=False),
        sa.Column("style", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("openings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("phrases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            "char_length(description) BETWEEN 1 AND 1000",
            name=op.f("ck_bots_description_length"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 80", name=op.f("ck_bots_name_length")
        ),
        sa.CheckConstraint(
            "target_elo BETWEEN 800 AND 2800", name=op.f("ck_bots_target_elo_range")
        ),
        sa.CheckConstraint(
            "(visibility = 'public' AND owner_id IS NULL) OR "
            "(visibility = 'private' AND owner_id IS NOT NULL)",
            name=op.f("ck_bots_visibility_owner"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_bots_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bots")),
    )
    op.create_index(
        "ix_bots_owner_id_created_at", "bots", ["owner_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_bots_visibility_created_at",
        "bots",
        ["visibility", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bots_visibility_created_at", table_name="bots")
    op.drop_index("ix_bots_owner_id_created_at", table_name="bots")
    op.drop_table("bots")
    bot_visibility_enum.drop(op.get_bind(), checkfirst=True)
