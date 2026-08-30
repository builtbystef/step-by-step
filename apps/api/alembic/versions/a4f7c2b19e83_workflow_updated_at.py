from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4f7c2b19e83"
down_revision: str | Sequence[str] | None = "3d5d33364927"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.drop_column("workflows", "updated_at")
