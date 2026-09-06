"""Add in-app support tickets and unread markers.

Revision ID: 20260906_0012
Revises: 20260905_0011
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0012"
down_revision: str | Sequence[str] | None = "20260905_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("user_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("category IN ('problem', 'idea', 'question')", name=op.f("ck_support_tickets_category_allowed")),
        sa.CheckConstraint("status IN ('open', 'waiting_user', 'closed')", name=op.f("ck_support_tickets_status_allowed")),
        sa.CheckConstraint("char_length(subject) BETWEEN 5 AND 160", name=op.f("ck_support_tickets_subject_length")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_support_tickets_owner_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_tickets")),
    )
    op.create_index("ix_support_tickets_owner_updated_at", "support_tickets", ["owner_id", "updated_at"])
    op.create_index("ix_support_tickets_status_updated_at", "support_tickets", ["status", "updated_at"])
    op.create_table(
        "support_messages",
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("author_role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("author_role IN ('user', 'admin')", name=op.f("ck_support_messages_author_role_allowed")),
        sa.CheckConstraint("char_length(content) BETWEEN 1 AND 5000", name=op.f("ck_support_messages_content_length")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_support_messages_author_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], name=op.f("fk_support_messages_ticket_id_support_tickets"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_messages")),
    )
    op.create_index("ix_support_messages_ticket_created_at", "support_messages", ["ticket_id", "created_at"])
    op.create_index("ix_support_messages_author_created_at", "support_messages", ["author_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_support_messages_author_created_at", table_name="support_messages")
    op.drop_index("ix_support_messages_ticket_created_at", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_status_updated_at", table_name="support_tickets")
    op.drop_index("ix_support_tickets_owner_updated_at", table_name="support_tickets")
    op.drop_table("support_tickets")
