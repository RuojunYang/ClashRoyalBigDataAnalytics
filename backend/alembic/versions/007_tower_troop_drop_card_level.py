"""tower troops reference table; participant tower_card_id; drop deck card_level

Revision ID: 007
Revises: 006
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tower_troops",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    tower_troops_table = sa.table(
        "tower_troops",
        sa.column("id", sa.BigInteger),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        tower_troops_table,
        [
            {"id": 159000000, "name": "Tower Princess"},
            {"id": 159000001, "name": "Cannoneer"},
            {"id": 159000002, "name": "Dagger Duchess"},
            {"id": 159000004, "name": "Royal Chef"},
        ],
    )

    op.add_column("battle_participants", sa.Column("tower_card_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "battle_participants_tower_card_id_fkey",
        "battle_participants",
        "tower_troops",
        ["tower_card_id"],
        ["id"],
    )
    op.create_index("idx_bp_tower_card", "battle_participants", ["tower_card_id"], unique=False)

    op.drop_column("battle_deck_cards", "card_level")


def downgrade() -> None:
    op.add_column(
        "battle_deck_cards",
        sa.Column("card_level", sa.SmallInteger(), nullable=True),
    )

    op.drop_index("idx_bp_tower_card", table_name="battle_participants")
    op.drop_constraint("battle_participants_tower_card_id_fkey", "battle_participants", type_="foreignkey")
    op.drop_column("battle_participants", "tower_card_id")

    op.drop_table("tower_troops")
