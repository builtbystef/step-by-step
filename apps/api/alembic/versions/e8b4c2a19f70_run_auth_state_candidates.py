from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8b4c2a19f70"
down_revision: str | Sequence[str] | None = "d5e8a1c04b73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def closed_enum(name: str, values: list[str], length: int) -> sa.Enum:
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        length=length,
        create_constraint=True,
    )


def upgrade() -> None:
    op.create_table(
        "run_auth_state_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column(
            "consent_scope",
            closed_enum("auth_state_consent_scope", ["organization", "personal"], 16),
            nullable=True,
        ),
        sa.Column("consenting_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["consenting_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "domain",
            name="run_auth_state_candidates_run_domain_key",
        ),
    )
    op.create_index(
        op.f("ix_run_auth_state_candidates_run_id"),
        "run_auth_state_candidates",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_run_auth_state_candidates_run_id"),
        table_name="run_auth_state_candidates",
    )
    op.drop_table("run_auth_state_candidates")
