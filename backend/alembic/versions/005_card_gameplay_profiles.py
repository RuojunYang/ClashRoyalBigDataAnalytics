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
    profiles_table = sa.table(
        "card_gameplay_profiles",
        sa.column("card_id", sa.BigInteger),
        sa.column("variant", sa.String),
        sa.column("role_code", sa.String),
        sa.column("is_core", sa.Boolean),
        sa.column("related_card_id", sa.BigInteger),
        sa.column("notes", sa.Text),
    )

    # Inline seed data — migrations must not import app modules that change later.
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
    card_gameplay_profiles = [
        {"card_id": 26000003, "variant": "base", "role_code": "tower_tank", "is_core": True, "notes": "Giant"},
        {"card_id": 26000009, "variant": "base", "role_code": "tower_tank", "is_core": True, "notes": "Golem"},
        {"card_id": 26000038, "variant": "base", "role_code": "support_tank", "is_core": False, "notes": "Ice Golem"},
        {"card_id": 26000021, "variant": "base", "role_code": "building_target", "is_core": True, "notes": "Hog Rider"},
        {"card_id": 27000009, "variant": "base", "role_code": "spawner", "is_core": False, "notes": "Tombstone"},
        {
            "card_id": 27000009,
            "variant": "hero",
            "role_code": "summoned_threat",
            "is_core": True,
            "notes": "Tombstone Hero form summons a major threat",
        },
        {
            "card_id": 28000004,
            "variant": "base",
            "role_code": "spell_win_condition",
            "is_core": True,
            "notes": "Goblin Barrel — spell win condition",
        },
    ]

    op.bulk_insert(roles_table, card_threat_roles)
    op.bulk_insert(
        profiles_table,
        [
            {
                "card_id": row["card_id"],
                "variant": row["variant"],
                "role_code": row["role_code"],
                "is_core": row["is_core"],
                "related_card_id": row.get("related_card_id"),
                "notes": row.get("notes"),
            }
            for row in card_gameplay_profiles
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_cgp_related_card", table_name="card_gameplay_profiles")
    op.drop_index("idx_cgp_role_code", table_name="card_gameplay_profiles")
    op.drop_index("idx_cgp_is_core", table_name="card_gameplay_profiles")
    op.drop_table("card_gameplay_profiles")
    op.drop_table("card_threat_roles")
