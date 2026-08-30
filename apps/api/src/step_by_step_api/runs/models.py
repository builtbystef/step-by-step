from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base


class RunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    BATCH = "batch"
    TEST = "test"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureReason(StrEnum):
    STEP_FAILED = "step_failed"
    AUTH_CHALLENGE = "auth_challenge"
    TAKEOVER_TIMEOUT = "takeover_timeout"
    TAKEOVER_ABANDONED = "takeover_abandoned"
    RUN_TIMEOUT = "run_timeout"
    WORKER_LOST = "worker_lost"
    MISSING_SECRET = "missing_secret"
    STARTUP_FAILED = "startup_failed"


class StepResultStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunControlKind(StrEnum):
    AUTOMATION = "automation"
    WAITING = "waiting"
    HUMAN = "human"
    VERIFYING = "verifying"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ArtifactKind(StrEnum):
    SCREENSHOT = "screenshot"
    TRACE = "trace"
    DOWNLOAD = "download"


class AuthStateConsentScope(StrEnum):
    ORGANIZATION = "organization"
    PERSONAL = "personal"


def enum_column(kind: type[StrEnum], name: str, length: int) -> Enum:
    return Enum(
        kind,
        native_enum=False,
        length=length,
        name=name,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


NON_TERMINAL = (
    RunStatus.QUEUED.value,
    RunStatus.RUNNING.value,
    RunStatus.WAITING_FOR_HUMAN.value,
)
DEFAULT_RUN_TIMEOUT_MS = 30 * 60 * 1000


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    starter_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int | None] = mapped_column(Integer, default=None)
    draft_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger: Mapped[RunTrigger] = mapped_column(
        enum_column(RunTrigger, "run_trigger", 16), default=RunTrigger.MANUAL
    )
    schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), index=True, default=None
    )
    batch_row_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("batch_rows.id", ondelete="SET NULL"), index=True, default=None
    )
    status: Mapped[RunStatus] = mapped_column(
        enum_column(RunStatus, "run_status", 32), default=RunStatus.QUEUED
    )
    failure_reason: Mapped[FailureReason | None] = mapped_column(
        enum_column(FailureReason, "run_failure_reason", 32), default=None
    )
    failure_detail: Mapped[str | None] = mapped_column(Text, default=None)
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=DEFAULT_RUN_TIMEOUT_MS)
    worker_id: Mapped[str | None] = mapped_column(String(200), default=None)
    worker_vnc_endpoint: Mapped[str | None] = mapped_column(String(500), default=None)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    pause_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handback_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    takeover_holder_session_id: Mapped[str | None] = mapped_column(
        String(64), default=None
    )
    takeover_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    auto_handback_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    automation_ms: Mapped[int] = mapped_column(BigInteger, default=0)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "version_number"],
            ["workflow_versions.workflow_id", "workflow_versions.number"],
            ondelete="CASCADE",
            name="runs_version_fkey",
        ),
        Index(
            "ix_runs_org_takeover_attention",
            "org_id",
            "takeover_deadline_at",
            postgresql_where=text(
                "status IN ('queued', 'running', 'waiting_for_human')"
            ),
        ),
        Index("ix_runs_org_queued_id", "org_id", "queued_at", "id"),
    )


class StepResult(Base):
    __tablename__ = "step_results"
    __table_args__ = (
        UniqueConstraint("run_id", "position", name="step_results_run_position_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[UUID] = mapped_column()
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[StepResultStatus] = mapped_column(
        enum_column(StepResultStatus, "step_result_status", 16)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    matched_candidate_rank: Mapped[int | None] = mapped_column(Integer)
    candidate_count: Mapped[int | None] = mapped_column(Integer)
    completed_by_human: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    diagnostics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extracted_value: Mapped[Any | None] = mapped_column(JSONB)


class RunControlInterval(Base):
    __tablename__ = "run_control_intervals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[RunControlKind] = mapped_column(
        enum_column(RunControlKind, "run_control_kind", 16)
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunTakeoverTicket(Base):
    __tablename__ = "run_takeover_tickets"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunLogLine(Base):
    __tablename__ = "run_log_lines"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="run_log_lines_run_seq_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    step_id: Mapped[UUID | None] = mapped_column(default=None)
    level: Mapped[LogLevel] = mapped_column(enum_column(LogLevel, "run_log_level", 16))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(Text)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[UUID | None] = mapped_column(default=None)
    kind: Mapped[ArtifactKind] = mapped_column(
        enum_column(ArtifactKind, "artifact_kind", 16)
    )
    object_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    index: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class RunAuthStateCandidate(Base):
    __tablename__ = "run_auth_state_candidates"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "domain", name="run_auth_state_candidates_run_domain_key"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    domain: Mapped[str] = mapped_column(String(253))
    consent_scope: Mapped[AuthStateConsentScope | None] = mapped_column(
        enum_column(AuthStateConsentScope, "auth_state_consent_scope", 16),
        default=None,
        nullable=True,
    )
    consenting_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
