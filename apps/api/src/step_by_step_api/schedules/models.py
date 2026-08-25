"""The Schedule table: one cron trigger owned by a Workflow and its Organization."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base

SKIP_OVERLAP = "overlap"
"""The only skip reason this slice records: a non-terminal Run of this Schedule."""


class Schedule(Base):
    """A cron-based trigger. Firing always executes the latest published Version."""

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
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_skip_reason: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
