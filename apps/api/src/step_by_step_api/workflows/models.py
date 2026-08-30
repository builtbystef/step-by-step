from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base

NAME_LENGTH = 200

DEFAULT_STEP_TIMEOUT_MS = 30_000

DEFAULT_TAKEOVER_TIMEOUT_MS = 30 * 60 * 1000


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(NAME_LENGTH))
    default_step_timeout_ms: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_STEP_TIMEOUT_MS
    )
    takeover_timeout_ms: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_TAKEOVER_TIMEOUT_MS
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowDraft(Base):
    __tablename__ = "workflow_drafts"

    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True
    )
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecordingMode(StrEnum):
    RECORD = "record"
    REPICK = "repick"


class RecordingSession(Base):
    __tablename__ = "recording_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_drafts.workflow_id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mode: Mapped[RecordingMode] = mapped_column(
        Enum(
            RecordingMode,
            native_enum=False,
            length=16,
            name="recording_mode",
            create_constraint=True,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    step_id: Mapped[UUID | None] = mapped_column(default=None)
    checkpoint_seq: Mapped[int | None] = mapped_column(Integer, default=None)
    checkpoint_steps: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, default=None
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
