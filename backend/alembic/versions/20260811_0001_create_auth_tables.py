"""Create authentication tables.

Revision ID: 20260811_0001
Revises:
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260811_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_status_enum = postgresql.ENUM(
    "active", "blocked", "deleted", name="user_status", create_type=False
)
system_role_enum = postgresql.ENUM(
    "user", "admin", name="system_role", create_type=False
)
auth_token_type_enum = postgresql.ENUM(
    "email_verification",
    "password_reset",
    name="auth_token_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    user_status_enum.create(bind, checkfirst=True)
    system_role_enum.create(bind, checkfirst=True)
    auth_token_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=True),
        sa.Column("status", user_status_enum, server_default="active", nullable=False),
        sa.Column("system_role", system_role_enum, server_default="user", nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_normalized")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "identities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
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
            "(provider = 'password' AND password_hash IS NOT NULL) OR "
            "(provider <> 'password' AND password_hash IS NULL)",
            name=op.f("ck_identities_password_hash_matches_provider"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_identities_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identities"),
        sa.UniqueConstraint(
            "provider", "provider_subject", name="uq_identities_provider_subject"
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_identities_user_provider"),
    )
    op.create_index("ix_identities_user_id", "identities", ["user_id"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_hash", sa.LargeBinary(length=32), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "octet_length(csrf_token_hash) = 32",
            name=op.f("ck_auth_sessions_csrf_token_hash_length"),
        ),
        sa.CheckConstraint(
            "expires_at <= absolute_expires_at", name=op.f("ck_auth_sessions_expiry_order")
        ),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32", name=op.f("ck_auth_sessions_token_hash_length")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user_id_revoked_at",
        "auth_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )

    op.create_table(
        "auth_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", auth_token_type_enum, nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name=op.f("ck_auth_tokens_consumed_after_creation"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_auth_tokens_expires_after_creation")
        ),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32", name=op.f("ck_auth_tokens_token_hash_length")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_tokens_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index(
        "ix_auth_tokens_user_id_type", "auth_tokens", ["user_id", "type"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_user_id_type", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_index("ix_auth_sessions_user_id_revoked_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_identities_user_id", table_name="identities")
    op.drop_table("identities")
    op.drop_table("users")

    bind = op.get_bind()
    auth_token_type_enum.drop(bind, checkfirst=True)
    system_role_enum.drop(bind, checkfirst=True)
    user_status_enum.drop(bind, checkfirst=True)
