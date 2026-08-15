"""Add persistent user games and analyses.

Revision ID: 20260815_0006
Revises: 20260813_0005
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0006"
down_revision: str | Sequence[str] | None = "20260813_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

game_source_enum = postgresql.ENUM(
    "chesscom", "bot", "pgn", name="game_source", create_type=False
)
analysis_status_enum = postgresql.ENUM(
    "pending",
    "completed",
    "failed",
    "cancelled",
    name="analysis_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    game_source_enum.create(bind, checkfirst=True)
    analysis_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "games",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source", game_source_enum, nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("pgn", sa.Text(), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
            "char_length(pgn) BETWEEN 1 AND 2000000",
            name=op.f("ck_games_pgn_length"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_games_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_games")),
        sa.UniqueConstraint(
            "owner_id",
            "source",
            "external_id",
            name="uq_games_owner_source_external",
        ),
    )
    op.create_index(
        "ix_games_owner_created_at", "games", ["owner_id", "created_at"]
    )
    op.create_index(
        "ix_games_owner_played_at", "games", ["owner_id", "played_at"]
    )

    op.create_table(
        "analyses",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("status", analysis_status_enum, nullable=False),
        sa.Column(
            "engine_result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("coach_response", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_analyses_game_id_games"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_analyses_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyses")),
    )
    op.create_index(
        "ix_analyses_game_created_at", "analyses", ["game_id", "created_at"]
    )
    op.create_index(
        "ix_analyses_owner_created_at", "analyses", ["owner_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_analyses_owner_created_at", table_name="analyses")
    op.drop_index("ix_analyses_game_created_at", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_games_owner_played_at", table_name="games")
    op.drop_index("ix_games_owner_created_at", table_name="games")
    op.drop_table("games")
    analysis_status_enum.drop(op.get_bind(), checkfirst=True)
    game_source_enum.drop(op.get_bind(), checkfirst=True)
