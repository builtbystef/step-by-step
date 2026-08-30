from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c8e1a2b7d0"
down_revision: str | Sequence[str] | None = "e3a79b8c2410"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("cron", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_skip_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedules_org_id", "schedules", ["org_id"])
    op.create_index("ix_schedules_workflow_id", "schedules", ["workflow_id"])
    op.create_index(
        "ix_schedules_due",
        "schedules",
        ["next_due_at"],
        postgresql_where=sa.text("enabled"),
    )
    op.create_foreign_key(
        "runs_schedule_id_fkey",
        "runs",
        "schedules",
        ["schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_runs_schedule_id", "runs", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_schedule_id", table_name="runs")
    op.drop_constraint("runs_schedule_id_fkey", "runs", type_="foreignkey")
    op.drop_index("ix_schedules_due", table_name="schedules")
    op.drop_index("ix_schedules_workflow_id", table_name="schedules")
    op.drop_index("ix_schedules_org_id", table_name="schedules")
    op.drop_table("schedules")
