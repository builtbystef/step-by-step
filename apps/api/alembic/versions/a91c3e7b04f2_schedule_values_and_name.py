"""Schedule values and name

A Schedule owns its non-secret Variable values and an optional name, so two
Schedules of one Workflow can do different work.

Revision ID: a91c3e7b04f2
Revises: f4c8e1a2b7d0
Create Date: 2026-08-25 17:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a91c3e7b04f2"
down_revision: str | Sequence[str] | None = "f4c8e1a2b7d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the Schedule's name and its non-secret value set."""
    op.add_column("schedules", sa.Column("name", sa.String(length=200), nullable=True))
    op.add_column(
        "schedules",
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column("schedules", "variables", server_default=None)


def downgrade() -> None:
    op.drop_column("schedules", "variables")
    op.drop_column("schedules", "name")
