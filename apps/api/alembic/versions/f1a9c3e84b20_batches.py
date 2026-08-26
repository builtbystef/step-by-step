"""Batches and batch rows

Revision ID: f1a9c3e84b20
Revises: e8b4c2a19f70
Create Date: 2026-08-26 11:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a9c3e84b20"
down_revision: str | Sequence[str] | None = "e8b4c2a19f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def closed_enum(name: str, values: list[str], length: int) -> sa.Enum:
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        length=length,
        create_constraint=True,
    )


def upgrade() -> None:
    """Add Batches and point a Run's batch_row_id at a row."""
    op.create_table(
        "batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batches_org_id", "batches", ["org_id"])
    op.create_index("ix_batches_workflow_id", "batches", ["workflow_id"])
    op.create_table(
        "batch_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            closed_enum(
                "batch_row_status",
                [
                    "queued",
                    "running",
                    "succeeded",
                    "failed",
                    "skipped",
                    "cancelled",
                ],
                16,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "index", name="batch_rows_batch_id_index_key"),
    )
    op.create_index("ix_batch_rows_batch_id", "batch_rows", ["batch_id"])
    op.create_foreign_key(
        "runs_batch_row_id_fkey",
        "runs",
        "batch_rows",
        ["batch_row_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_runs_batch_row_id", "runs", ["batch_row_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_batch_row_id", table_name="runs")
    op.drop_constraint("runs_batch_row_id_fkey", "runs", type_="foreignkey")
    op.drop_index("ix_batch_rows_batch_id", table_name="batch_rows")
    op.drop_table("batch_rows")
    op.drop_index("ix_batches_workflow_id", table_name="batches")
    op.drop_index("ix_batches_org_id", table_name="batches")
    op.drop_table("batches")
