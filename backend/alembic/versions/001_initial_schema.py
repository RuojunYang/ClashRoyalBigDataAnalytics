"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cards",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("elixir_cost", sa.Integer(), nullable=True),
        sa.Column("max_evolution_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_evolution", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_hero", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("card_type", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cards_elixir", "cards", ["elixir_cost"], unique=False)
    op.create_index("idx_cards_type", "cards", ["card_type"], unique=False)

    op.create_table(
        "card_changelog",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("field_name", sa.String(length=32), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("sync_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_changelog_card", "card_changelog", ["card_id", sa.text("changed_at DESC")], unique=False)

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sync_type", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("cards_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cards_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cards_deactivated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changes_logged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sync_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_index("idx_changelog_card", table_name="card_changelog")
    op.drop_table("card_changelog")
    op.drop_index("idx_cards_type", table_name="cards")
    op.drop_index("idx_cards_elixir", table_name="cards")
    op.drop_table("cards")
