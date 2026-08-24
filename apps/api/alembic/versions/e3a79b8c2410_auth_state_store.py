"""Auth State store

Revision ID: e3a79b8c2410
Revises: d2f648a719c3
Create Date: 2026-08-24 07:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3a79b8c2410"
down_revision: str | Sequence[str] | None = "d2f648a719c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Organization Auth State and member Personal Overrides."""
    op.create_table(
        "auth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("sealed_blob", sa.LargeBinary(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["org_id", "user_id"],
            ["memberships.org_id", "memberships.user_id"],
            name="auth_states_membership_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id",
            "user_id",
            "domain",
            name="auth_states_personal_domain_key",
        ),
    )
    op.create_index(
        "auth_states_organization_domain_key",
        "auth_states",
        ["org_id", "domain"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_index(
        op.f("ix_auth_states_org_id"), "auth_states", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_auth_states_user_id"), "auth_states", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Remove Auth State storage."""
    op.drop_index(op.f("ix_auth_states_user_id"), table_name="auth_states")
    op.drop_index(op.f("ix_auth_states_org_id"), table_name="auth_states")
    op.drop_index("auth_states_organization_domain_key", table_name="auth_states")
    op.drop_table("auth_states")
