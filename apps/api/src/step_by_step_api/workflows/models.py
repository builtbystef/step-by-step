"""The Workflow tables: the Workflow itself, its one Draft, and its Versions.

Three tables rather than one, because the Draft is one of a family: a Version
stores the same document shape, and a list screen must be able to read a
Workflow's name without dragging a two-hundred-Step document along with it.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base

NAME_LENGTH = 200
"""As long as an Organization's name; a Workflow name is a title, not prose."""

DEFAULT_STEP_TIMEOUT_MS = 30_000
"""How long a Step may take before it fails, unless the Step overrides it."""

DEFAULT_TAKEOVER_TIMEOUT_MS = 30 * 60 * 1000
"""How long a paused Run waits for the human who has to finish something."""


class Workflow(Base):
    """A named sequence of Steps, owned by one Organization.

    Both timeouts are written into the row at creation rather than left to a
    default somewhere else: a Run must be able to read what this Workflow
    waits for without knowing which library version wrote it.
    """

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
    """When the Workflow itself was last touched — a rename, and nothing else
    so far. Editing the document moves the Draft's stamp rather than this one,
    so a list sorting by activity reads the later of the two."""


class WorkflowDraft(Base):
    """The single mutable document of one Workflow.

    One row per Workflow, and saving replaces the document whole. The database
    cannot see inside the JSONB, so every rule about what is in it — step-id
    uniqueness, declared Variables, payload shape — is enforced at the save.
    """

    __tablename__ = "workflow_drafts"

    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True
    )
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecordingMode(StrEnum):
    """Whether a recording session replaces the Draft or repairs one Step."""

    RECORD = "record"
    REPICK = "repick"


class RecordingSession(Base):
    """A short-lived capability scoped to one user and one Workflow Draft."""

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
    """One published document of a Workflow, numbered and never rewritten.

    The number is the Workflow's own count rather than a global sequence —
    "version 3" is what a user says about their Workflow — so the key is the
    pair, and the database refuses a number that was already minted whatever
    two concurrent publishes believed.

    There is no updated_at, and no route writes to this table after the
    insert. A Version that could change is a Run that cannot be explained.
    """

    __tablename__ = "workflow_versions"

    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
