"""Add administrator messages, announcements and welcome threads.

Revision ID: 20260913_0015
Revises: 20260909_0014
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0015"
down_revision: str | Sequence[str] | None = "20260909_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
            "char_length(title) BETWEEN 5 AND 160",
            name=op.f("ck_announcements_title_length"),
        ),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 1 AND 5000",
            name=op.f("ck_announcements_content_length"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_announcements_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcements")),
    )
    op.create_index(
        "ix_announcements_published_at", "announcements", ["published_at"]
    )

    op.drop_constraint(
        op.f("ck_support_tickets_category_allowed"),
        "support_tickets",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_support_tickets_category_allowed"),
        "support_tickets",
        "category IN ('problem', 'idea', 'question', 'message')",
    )
    op.add_column(
        "support_tickets",
        sa.Column(
            "initiated_by", sa.String(length=16), server_default="user", nullable=False
        ),
    )
    op.add_column(
        "support_tickets", sa.Column("welcome_key", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "support_tickets",
        sa.Column("source_announcement_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_support_tickets_initiated_by_allowed"),
        "support_tickets",
        "initiated_by IN ('user', 'admin', 'system')",
    )
    op.create_unique_constraint(
        op.f("uq_support_welcome_owner"),
        "support_tickets",
        ["owner_id", "welcome_key"],
    )
    op.create_unique_constraint(
        op.f("uq_support_announcement_owner"),
        "support_tickets",
        ["owner_id", "source_announcement_id"],
    )
    op.create_foreign_key(
        op.f("fk_support_tickets_source_announcement_id_announcements"),
        "support_tickets",
        "announcements",
        ["source_announcement_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "announcement_reads",
        sa.Column("announcement_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["announcement_id"],
            ["announcements.id"],
            name=op.f("fk_announcement_reads_announcement_id_announcements"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_announcement_reads_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "announcement_id", "user_id", name=op.f("pk_announcement_reads")
        ),
    )


def downgrade() -> None:
    op.drop_table("announcement_reads")
    op.drop_constraint(
        op.f("fk_support_tickets_source_announcement_id_announcements"),
        "support_tickets",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_support_announcement_owner"),
        "support_tickets",
        type_="unique",
    )
    op.drop_constraint(
        op.f("uq_support_welcome_owner"),
        "support_tickets",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_support_tickets_initiated_by_allowed"),
        "support_tickets",
        type_="check",
    )
    op.drop_column("support_tickets", "source_announcement_id")
    op.drop_column("support_tickets", "welcome_key")
    op.drop_column("support_tickets", "initiated_by")
    op.drop_constraint(
        op.f("ck_support_tickets_category_allowed"),
        "support_tickets",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_support_tickets_category_allowed"),
        "support_tickets",
        "category IN ('problem', 'idea', 'question')",
    )
    op.drop_index("ix_announcements_published_at", table_name="announcements")
    op.drop_table("announcements")
