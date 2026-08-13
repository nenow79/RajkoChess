"""Add time-bound plan grants and persistent usage events.

Revision ID: 20260813_0005
Revises: 20260812_0004
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0005"
down_revision: str | Sequence[str] | None = "20260812_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_grants",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_key", sa.String(length=32), server_default="premium", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_plan_grants_ends_after_start")),
        sa.CheckConstraint("plan_key = 'premium'", name=op.f("ck_plan_grants_supported_plan")),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], name=op.f("fk_plan_grants_granted_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_plan_grants_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_grants")),
    )
    op.create_index("ix_plan_grants_user_period", "plan_grants", ["user_id", "starts_at", "ends_at"], unique=False)

    op.create_table(
        "usage_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("plan_key", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_usage_events_quantity_positive")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_usage_events_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_events")),
    )
    op.create_index("ix_usage_events_user_key_occurred", "usage_events", ["user_id", "key", "occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_usage_events_user_key_occurred", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_index("ix_plan_grants_user_period", table_name="plan_grants")
    op.drop_table("plan_grants")
