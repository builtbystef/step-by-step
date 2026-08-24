"""Secret vault

Revision ID: b7312f4d990a
Revises: a4f7c2b19e83
Create Date: 2026-08-24 06:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7312f4d990a"
down_revision: str | Sequence[str] | None = "a4f7c2b19e83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Organization Secrets and member Personal Overrides."""
    op.create_table(
        "secrets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sealed_value", sa.LargeBinary(), nullable=False),
        sa.Column("sealed_data_key", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="secrets_org_name_key"),
    )
    op.create_index(op.f("ix_secrets_org_id"), "secrets", ["org_id"], unique=False)
    op.create_table(
        "secret_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("secret_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sealed_value", sa.LargeBinary(), nullable=False),
        sa.Column("sealed_data_key", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["secret_id"], ["secrets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "secret_id", "user_id", name="secret_overrides_secret_user_key"
        ),
    )
    op.create_index(
        op.f("ix_secret_overrides_secret_id"),
        "secret_overrides",
        ["secret_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_secret_overrides_user_id"),
        "secret_overrides",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the Secret vault."""
    op.drop_index(op.f("ix_secret_overrides_user_id"), table_name="secret_overrides")
    op.drop_index(op.f("ix_secret_overrides_secret_id"), table_name="secret_overrides")
    op.drop_table("secret_overrides")
    op.drop_index(op.f("ix_secrets_org_id"), table_name="secrets")
    op.drop_table("secrets")
