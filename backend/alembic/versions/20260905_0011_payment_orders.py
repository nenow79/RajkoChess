"""Add manual bank-transfer payment orders.

Revision ID: 20260905_0011
Revises: 20260829_0010
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0011"
down_revision: str | Sequence[str] | None = "20260829_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reference_code", sa.String(length=16), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="PLN", nullable=False
        ),
        sa.Column("premium_days", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(length=160), nullable=False),
        sa.Column("iban", sa.String(length=34), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="pending", nullable=False
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("plan_grant_id", sa.Uuid(), nullable=True),
        sa.Column("admin_note", sa.String(length=1000), nullable=True),
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
            "amount_minor > 0", name=op.f("ck_payment_orders_amount_positive")
        ),
        sa.CheckConstraint(
            "currency = 'PLN'", name=op.f("ck_payment_orders_currency_pln")
        ),
        sa.CheckConstraint(
            "premium_days BETWEEN 1 AND 366",
            name=op.f("ck_payment_orders_premium_days_range"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')",
            name=op.f("ck_payment_orders_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_payment_orders_confirmed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plan_grant_id"],
            ["plan_grants.id"],
            name=op.f("fk_payment_orders_plan_grant_id_plan_grants"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_payment_orders_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_orders")),
        sa.UniqueConstraint("plan_grant_id", name=op.f("uq_payment_orders_plan_grant_id")),
        sa.UniqueConstraint("reference_code", name=op.f("uq_payment_orders_reference_code")),
    )
    op.create_index(
        "ix_payment_orders_status_created_at",
        "payment_orders",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_payment_orders_one_pending_per_user",
        "payment_orders",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_payment_orders_one_pending_per_user", table_name="payment_orders")
    op.drop_index("ix_payment_orders_status_created_at", table_name="payment_orders")
    op.drop_table("payment_orders")
