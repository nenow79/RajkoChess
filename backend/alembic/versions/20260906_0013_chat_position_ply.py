"""store the selected game position with chat messages

Revision ID: 20260906_0013
Revises: 20260906_0012
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0013"
down_revision: str | Sequence[str] | None = "20260906_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("position_ply", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_chat_messages_position_ply_range",
        "chat_messages",
        "position_ply IS NULL OR position_ply BETWEEN 0 AND 600",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_chat_messages_position_ply_range",
        "chat_messages",
        type_="check",
    )
    op.drop_column("chat_messages", "position_ply")
