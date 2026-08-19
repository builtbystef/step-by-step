"""workflow updated_at

The Workflow's own last-touched stamp, which the list's activity sort reads
beside the Draft's. Existing rows take their creation time: nothing has been
renamed yet, so that is exactly when each was last touched.

Revision ID: a4f7c2b19e83
Revises: 3d5d33364927
Create Date: 2026-08-19 19:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4f7c2b19e83"
down_revision: str | Sequence[str] | None = "3d5d33364927"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "workflows",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute("UPDATE workflows SET updated_at = created_at")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workflows", "updated_at")
