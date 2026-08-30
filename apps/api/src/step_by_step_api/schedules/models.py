from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base

from step_by_step_api.runs.models import enum_column

GRACE_WINDOW_SECONDS = 120
OCCURRENCE_PRUNE_DEPTH = 500


class OccurrenceReason(StrEnum):
    OVERLAP = "overlap"
    MISSED = "missed"
    MISSING_VALUES = "missing_values"


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        Index(
            "ix_schedules_due",
            "next_due_at",
            postgresql_where=text("enabled"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(200), default=None)
    cron: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(default=True)
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScheduleOccurrence(Base):
    __tablename__ = "schedule_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "occurrence_at",
            name="schedule_occurrences_schedule_id_occurrence_at_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    schedule_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), index=True
    )
    occurrence_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[OccurrenceReason] = mapped_column(
        enum_column(OccurrenceReason, "occurrence_reason", 16)
    )
    blocking_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
