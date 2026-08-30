from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3d5d33364927"
down_revision: str | Sequence[str] | None = "64c6b5193390"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signin_code_issuance",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("issued", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("signin_code_issuance")
