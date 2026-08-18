"""The Workflow tables: the Workflow itself, and its one Draft.

Two rows rather than one, because the Draft is the first of a family: a
Version stores the same document shape, and a list screen must be able to read
a Workflow's name without dragging a two-hundred-Step document along with it.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
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
