"""workflow versions

The immutable half of the document store: one row per published Version,
keyed by the Workflow and the number it carries there, so that two publishes
racing for the same number leave one of them refused by the key rather than
both minted.

Revision ID: 9d10b661a9f4
Revises: 1be493f219da
Create Date: 2026-08-18 19:34:25.168141

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9d10b661a9f4"
down_revision: str | Sequence[str] | None = "1be493f219da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workflow_versions",
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workflow_id", "number"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("workflow_versions")
