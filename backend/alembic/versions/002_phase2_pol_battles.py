"""phase 2 pol leaderboard and battles

Revision ID: 002
Revises: 001
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("tag", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("latest_elo_rating", sa.Integer(), nullable=True),
        sa.Column("latest_rank", sa.Integer(), nullable=True),
        sa.Column("exp_level", sa.Integer(), nullable=True),
        sa.Column("clan_tag", sa.String(length=16), nullable=True),
        sa.Column("clan_name", sa.String(length=64), nullable=True),
        sa.Column("is_tracked", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_leaderboard_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_battlelog_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("tag"),
    )
    op.create_index("idx_players_tracked", "players", ["is_tracked"], unique=False)

    op.create_table(
        "leaderboard_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="global_pol"),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("top_n", sa.Integer(), nullable=False),
        sa.Column("entries_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="success"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "leaderboard_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("player_tag", sa.String(length=16), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("elo_rating", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("exp_level", sa.Integer(), nullable=True),
        sa.Column("clan_tag", sa.String(length=16), nullable=True),
        sa.Column("clan_name", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["snapshot_id"], ["leaderboard_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "player_tag", name="uq_leaderboard_entry_snapshot_player"),
    )
    op.create_index("idx_le_snapshot_rank", "leaderboard_entries", ["snapshot_id", "rank"], unique=False)
    op.create_index("idx_le_player_tag", "leaderboard_entries", ["player_tag"], unique=False)

    op.create_table(
        "battles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("battle_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("battle_type", sa.String(length=32), nullable=True),
        sa.Column("game_mode_id", sa.Integer(), nullable=True),
        sa.Column("game_mode_name", sa.String(length=64), nullable=True),
        sa.Column("arena_id", sa.Integer(), nullable=True),
        sa.Column("arena_name", sa.String(length=64), nullable=True),
        sa.Column("league_number", sa.Integer(), nullable=True),
        sa.Column("battle_key", sa.String(length=128), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("battle_key"),
    )
    op.create_index("idx_battles_time", "battles", ["battle_time"], unique=False)

    op.create_table(
        "battle_participants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("battle_id", sa.Integer(), nullable=False),
        sa.Column("player_tag", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("starting_trophies", sa.Integer(), nullable=True),
        sa.Column("trophy_change", sa.Integer(), nullable=True),
        sa.Column("crowns", sa.Integer(), nullable=True),
        sa.Column("won", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["battle_id"], ["battles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bp_battle", "battle_participants", ["battle_id"], unique=False)
    op.create_index("idx_bp_player", "battle_participants", ["player_tag"], unique=False)

    op.create_table(
        "battle_deck_cards",
        sa.Column("battle_id", sa.Integer(), nullable=False),
        sa.Column("player_tag", sa.String(length=16), nullable=False),
        sa.Column("slot", sa.SmallInteger(), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("card_level", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["battle_id"], ["battles.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("battle_id", "player_tag", "slot"),
    )
    op.create_index("idx_bdc_card", "battle_deck_cards", ["card_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_bdc_card", table_name="battle_deck_cards")
    op.drop_table("battle_deck_cards")
    op.drop_index("idx_bp_player", table_name="battle_participants")
    op.drop_index("idx_bp_battle", table_name="battle_participants")
    op.drop_table("battle_participants")
    op.drop_index("idx_battles_time", table_name="battles")
    op.drop_table("battles")
    op.drop_index("idx_le_player_tag", table_name="leaderboard_entries")
    op.drop_index("idx_le_snapshot_rank", table_name="leaderboard_entries")
    op.drop_table("leaderboard_entries")
    op.drop_table("leaderboard_snapshots")
    op.drop_index("idx_players_tracked", table_name="players")
    op.drop_table("players")
