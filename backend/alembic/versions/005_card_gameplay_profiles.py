"""card threat roles and gameplay profiles

Revision ID: 005
Revises: 004
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_threat_roles",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "card_gameplay_profiles",
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("variant", sa.String(length=16), nullable=False),
        sa.Column("role_code", sa.String(length=32), nullable=False),
        sa.Column("is_core", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("related_card_id", sa.BigInteger(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["related_card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["role_code"], ["card_threat_roles.code"]),
        sa.PrimaryKeyConstraint("card_id", "variant"),
    )
    op.create_index("idx_cgp_is_core", "card_gameplay_profiles", ["is_core"], unique=False)
    op.create_index("idx_cgp_role_code", "card_gameplay_profiles", ["role_code"], unique=False)
    op.create_index("idx_cgp_related_card", "card_gameplay_profiles", ["related_card_id"], unique=False)

    roles_table = sa.table(
        "card_threat_roles",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("description", sa.Text),
    )

    card_threat_roles = [
        {
            "code": "tower_tank",
            "label": "Tower Tank",
            "description": "Heavy troop that primarily targets towers and anchors a push.",
        },
        {
            "code": "building_target",
            "label": "Building Target",
            "description": "Win condition that targets buildings directly (e.g. Hog, Balloon).",
        },
        {
            "code": "support_tank",
            "label": "Support Tank",
            "description": "Troop that soaks damage or distracts but is not the main win condition.",
        },
        {
            "code": "spawner",
            "label": "Spawner",
            "description": "Building or effect that produces units over time.",
        },
        {
            "code": "summoned_threat",
            "label": "Summoned Threat",
            "description": "Primary threat created by another card (hero skill, spawn, etc.).",
        },
        {
            "code": "spell_win_condition",
            "label": "Spell Win Condition",
            "description": "Spell that can serve as the deck's primary damage plan (e.g. Goblin Barrel).",
        },
        {
            "code": "spell_support",
            "label": "Spell Support",
            "description": "Spell that supports a push but is not the deck core on its own.",
        },
    ]

    op.bulk_insert(roles_table, card_threat_roles)


def downgrade() -> None:
    op.drop_index("idx_cgp_related_card", table_name="card_gameplay_profiles")
    op.drop_index("idx_cgp_role_code", table_name="card_gameplay_profiles")
    op.drop_index("idx_cgp_is_core", table_name="card_gameplay_profiles")
    op.drop_table("card_gameplay_profiles")
    op.drop_table("card_threat_roles")
