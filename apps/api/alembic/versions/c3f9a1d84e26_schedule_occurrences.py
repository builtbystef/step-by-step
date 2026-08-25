"""Schedule occurrences

A Schedule's holes — Occurrences that produced no Run — become rows, and
last_skip_reason is replaced by them. Disabling clears next_due_at.

Revision ID: c3f9a1d84e26
Revises: a91c3e7b04f2
Create Date: 2026-08-25 17:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f9a1d84e26"
down_revision: str | Sequence[str] | None = "a91c3e7b04f2"
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
    """Record non-firing Occurrences and drop last_skip_reason."""
    op.create_table(
        "schedule_occurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "reason",
            closed_enum(
                "occurrence_reason",
                ["overlap", "missed", "missing_values"],
                16,
            ),
            nullable=False,
        ),
        sa.Column("blocking_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocking_run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "schedule_id",
            "occurrence_at",
            name="schedule_occurrences_schedule_id_occurrence_at_key",
        ),
    )
    op.create_index(
        "ix_schedule_occurrences_schedule_id",
        "schedule_occurrences",
        ["schedule_id"],
    )
    op.drop_column("schedules", "last_skip_reason")
    op.alter_column("schedules", "next_due_at", existing_nullable=False, nullable=True)
    op.execute("UPDATE schedules SET next_due_at = NULL WHERE NOT enabled")


def downgrade() -> None:
    op.execute("UPDATE schedules SET next_due_at = now() WHERE next_due_at IS NULL")
    op.alter_column("schedules", "next_due_at", existing_nullable=True, nullable=False)
    op.add_column("schedules", sa.Column("last_skip_reason", sa.Text(), nullable=True))
    op.drop_index(
        "ix_schedule_occurrences_schedule_id", table_name="schedule_occurrences"
    )
    op.drop_table("schedule_occurrences")
