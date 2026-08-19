"""signin code issuance

One table: how many Sign-in Codes one address has been sent in its current
window, which is what the per-email issuance limit counts. Its own table
rather than a column on `signin_codes`, because the count has to outlive the
code — a code row goes the moment the code is spent.

Revision ID: 3d5d33364927
Revises: 64c6b5193390
Create Date: 2026-08-19 10:42:13.258845

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d5d33364927"
down_revision: str | Sequence[str] | None = "64c6b5193390"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "signin_code_issuance",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("issued", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("signin_code_issuance")
