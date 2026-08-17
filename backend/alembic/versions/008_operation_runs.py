"""operation runs audit log

Revision ID: 008
Revises: 007
Create Date: 2026-08-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("params", JSON, nullable=True),
        sa.Column("progress", JSON, nullable=True),
        sa.Column("result", JSON, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_operation_runs_operation", "operation_runs", ["operation"], unique=False)
    op.create_index("idx_operation_runs_started", "operation_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_operation_runs_started", table_name="operation_runs")
    op.drop_index("idx_operation_runs_operation", table_name="operation_runs")
    op.drop_table("operation_runs")
