"""Takeover tickets and the hand-back stamp

A waiting Run records who holds control and the single-use ticket that will
admit their VNC connection. Hand-back is a row stamp, same shape as pause
and cancel, so a dropped pub/sub message never hides it.

Revision ID: b8e4c1d07a92
Revises: c3f9a1d84e26
Create Date: 2026-08-25 18:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e4c1d07a92"
down_revision: str | Sequence[str] | None = "c3f9a1d84e26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Stamp hand-back on the Run and store takeover tickets."""
    op.add_column(
        "runs",
        sa.Column("handback_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "run_takeover_tickets",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_run_takeover_tickets_run_id"),
        "run_takeover_tickets",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop takeover tickets and the hand-back stamp."""
    op.drop_index(
        op.f("ix_run_takeover_tickets_run_id"), table_name="run_takeover_tickets"
    )
    op.drop_table("run_takeover_tickets")
    op.drop_column("runs", "handback_requested_at")
