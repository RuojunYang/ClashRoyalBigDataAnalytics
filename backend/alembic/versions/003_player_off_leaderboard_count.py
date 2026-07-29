"""add player off_leaderboard_count

Revision ID: 003
Revises: 002
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("off_leaderboard_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("players", "off_leaderboard_count", server_default=None)


def downgrade() -> None:
    op.drop_column("players", "off_leaderboard_count")
