"""The Batch and its rows. Counts are always derived from rows."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base

from step_by_step_api.runs.models import enum_column

NAME_LENGTH = 200


class BatchRowStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class Batch(Base):
    """One Workflow plus a list of input rows. Rows execute one at a time."""

    __tablename__ = "batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(NAME_LENGTH))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BatchRow(Base):
    """One input row. Status and output follow the latest attempt."""

    __tablename__ = "batch_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "index", name="batch_rows_batch_id_index_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer)
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[BatchRowStatus] = mapped_column(
        enum_column(BatchRowStatus, "batch_row_status", 16),
        default=BatchRowStatus.QUEUED,
    )
