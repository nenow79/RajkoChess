"""add Lichess as a game source

Revision ID: 20260909_0014
Revises: 20260906_0013
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260909_0014"
down_revision: str | Sequence[str] | None = "20260906_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE game_source ADD VALUE IF NOT EXISTS 'lichess'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove a single enum value while rows may use it.
    pass
