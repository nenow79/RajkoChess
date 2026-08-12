"""Mark accounts created before email verification as verified.

Revision ID: 20260812_0004
Revises: 20260811_0003
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0004"
down_revision: str | Sequence[str] | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE users SET email_verified_at = now(), updated_at = now() "
            "WHERE email_verified_at IS NULL"
        )
    )


def downgrade() -> None:
    # Weryfikacji nie można bezpiecznie cofnąć: po migracji mogły dojść nowe konta.
    pass
