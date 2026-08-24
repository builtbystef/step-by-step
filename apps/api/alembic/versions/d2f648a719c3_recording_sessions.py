"""Recording sessions

Revision ID: d2f648a719c3
Revises: c89e3b6a1f42
Create Date: 2026-08-24 07:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2f648a719c3"
down_revision: str | Sequence[str] | None = "c89e3b6a1f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recording_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "mode",
            sa.Enum(
                "record",
                "repick",
                name="recording_mode",
                native_enum=False,
                length=16,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("checkpoint_seq", sa.Integer(), nullable=True),
        sa.Column(
            "checkpoint_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflow_drafts.workflow_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_recording_sessions_user_id", "recording_sessions", ["user_id"])
    op.create_index(
        "ix_recording_sessions_workflow_id", "recording_sessions", ["workflow_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_recording_sessions_workflow_id", table_name="recording_sessions")
    op.drop_index("ix_recording_sessions_user_id", table_name="recording_sessions")
    op.drop_table("recording_sessions")
