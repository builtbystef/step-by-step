from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c89e3b6a1f42"
down_revision: str | Sequence[str] | None = "b7312f4d990a"
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
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("starter_user_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column(
            "draft_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column(
            "trigger",
            closed_enum("run_trigger", ["manual", "schedule", "batch", "test"], 16),
            nullable=False,
        ),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("batch_row_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            closed_enum(
                "run_status",
                [
                    "queued",
                    "running",
                    "waiting_for_human",
                    "succeeded",
                    "failed",
                    "cancelled",
                ],
                32,
            ),
            nullable=False,
        ),
        sa.Column(
            "failure_reason",
            closed_enum(
                "run_failure_reason",
                [
                    "step_failed",
                    "auth_challenge",
                    "takeover_timeout",
                    "takeover_abandoned",
                    "run_timeout",
                    "worker_lost",
                    "missing_secret",
                    "startup_failed",
                ],
                32,
            ),
            nullable=True,
        ),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timeout_ms", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("worker_vnc_endpoint", sa.String(length=500), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pause_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("takeover_holder_session_id", sa.String(length=64), nullable=True),
        sa.Column("takeover_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_handback_disabled", sa.Boolean(), nullable=False),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("automation_ms", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["starter_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_id", "version_number"],
            ["workflow_versions.workflow_id", "workflow_versions.number"],
            name="runs_version_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_org_id", "runs", ["org_id"], unique=False)
    op.create_index(
        "ix_runs_starter_user_id", "runs", ["starter_user_id"], unique=False
    )
    op.create_index("ix_runs_workflow_id", "runs", ["workflow_id"], unique=False)
    op.create_index(
        "ix_runs_org_queued_id", "runs", ["org_id", "queued_at", "id"], unique=False
    )
    op.create_index(
        "ix_runs_org_takeover_attention",
        "runs",
        ["org_id", "takeover_deadline_at"],
        unique=False,
        postgresql_where=sa.text(
            "status IN ('queued', 'running', 'waiting_for_human')"
        ),
    )

    op.create_table(
        "run_control_intervals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            closed_enum(
                "run_control_kind", ["automation", "waiting", "human", "verifying"], 16
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_run_control_intervals_run_id",
        "run_control_intervals",
        ["run_id"],
        unique=False,
    )

    op.create_table(
        "run_log_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column(
            "level",
            closed_enum("run_log_level", ["debug", "info", "warning", "error"], 16),
            nullable=False,
        ),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "seq", name="run_log_lines_run_seq_key"),
    )
    op.create_index(
        "ix_run_log_lines_run_id", "run_log_lines", ["run_id"], unique=False
    )

    op.create_table(
        "step_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            closed_enum("step_result_status", ["passed", "failed", "skipped"], 16),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matched_candidate_rank", sa.Integer(), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=True),
        sa.Column("completed_by_human", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "extracted_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "position", name="step_results_run_position_key"),
    )
    op.create_index("ix_step_results_run_id", "step_results", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_step_results_run_id", table_name="step_results")
    op.drop_table("step_results")
    op.drop_index("ix_run_log_lines_run_id", table_name="run_log_lines")
    op.drop_table("run_log_lines")
    op.drop_index("ix_run_control_intervals_run_id", table_name="run_control_intervals")
    op.drop_table("run_control_intervals")
    op.drop_index(
        "ix_runs_org_takeover_attention",
        table_name="runs",
        postgresql_where=sa.text(
            "status IN ('queued', 'running', 'waiting_for_human')"
        ),
    )
    op.drop_index("ix_runs_org_queued_id", table_name="runs")
    op.drop_index("ix_runs_workflow_id", table_name="runs")
    op.drop_index("ix_runs_starter_user_id", table_name="runs")
    op.drop_index("ix_runs_org_id", table_name="runs")
    op.drop_table("runs")
