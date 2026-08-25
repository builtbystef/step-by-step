"""Artifacts a Run leaves behind

Revision ID: d5e8a1c04b73
Revises: b8e4c1d07a92
Create Date: 2026-08-25 20:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e8a1c04b73"
down_revision: str | Sequence[str] | None = "b8e4c1d07a92"
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
    """Store screenshot, trace, and download Artifacts under a Run."""
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            closed_enum("artifact_kind", ["screenshot", "trace", "download"], 16),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artifacts_run_id"), "artifacts", ["run_id"], unique=False)


def downgrade() -> None:
    """Drop Artifacts."""
    op.drop_index(op.f("ix_artifacts_run_id"), table_name="artifacts")
    op.drop_table("artifacts")
