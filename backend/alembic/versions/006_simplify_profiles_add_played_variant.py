"""simplify profiles drop roles; add battle_deck_cards.played_variant

Revision ID: 006
Revises: 005
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_cgp_role_code", table_name="card_gameplay_profiles")
    op.drop_constraint(
        "card_gameplay_profiles_role_code_fkey",
        "card_gameplay_profiles",
        type_="foreignkey",
    )
    op.drop_column("card_gameplay_profiles", "role_code")
    op.drop_table("card_threat_roles")

    op.add_column(
        "battle_deck_cards",
        sa.Column("played_variant", sa.String(length=16), nullable=False, server_default="base"),
    )
    op.alter_column("battle_deck_cards", "played_variant", server_default=None)
    op.create_index("idx_bdc_played_variant", "battle_deck_cards", ["played_variant"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_bdc_played_variant", table_name="battle_deck_cards")
    op.drop_column("battle_deck_cards", "played_variant")

    op.create_table(
        "card_threat_roles",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.add_column(
        "card_gameplay_profiles",
        sa.Column("role_code", sa.String(length=32), nullable=False, server_default="tower_tank"),
    )
    op.create_foreign_key(
        "card_gameplay_profiles_role_code_fkey",
        "card_gameplay_profiles",
        "card_threat_roles",
        ["role_code"],
        ["code"],
    )
    op.create_index("idx_cgp_role_code", "card_gameplay_profiles", ["role_code"], unique=False)
    op.alter_column("card_gameplay_profiles", "role_code", server_default=None)
