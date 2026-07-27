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

    from app.data.card_profile_seed import CARD_GAMEPLAY_PROFILES, CARD_THREAT_ROLES

    op.bulk_insert(roles_table, CARD_THREAT_ROLES)
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
            for row in CARD_GAMEPLAY_PROFILES
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_cgp_related_card", table_name="card_gameplay_profiles")
    op.drop_index("idx_cgp_role_code", table_name="card_gameplay_profiles")
    op.drop_index("idx_cgp_is_core", table_name="card_gameplay_profiles")
    op.drop_table("card_gameplay_profiles")
    op.drop_table("card_threat_roles")
