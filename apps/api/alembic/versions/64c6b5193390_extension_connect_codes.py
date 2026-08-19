"""extension connect codes

One table: the outstanding one-time codes a signed-in user shows so that an
extension can pair with this instance. It holds a digest and never the code,
and a row goes with the user who took it.

Revision ID: 64c6b5193390
Revises: 9d10b661a9f4
Create Date: 2026-08-18 22:25:38.626124

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64c6b5193390"
down_revision: str | Sequence[str] | None = "9d10b661a9f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "extension_connect_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        op.f("ix_extension_connect_codes_user_id"),
        "extension_connect_codes",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_extension_connect_codes_user_id"), table_name="extension_connect_codes"
    )
    op.drop_table("extension_connect_codes")
