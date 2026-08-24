"""The Workflow HTTP surface: its Draft, and the Versions publishing mints.

Creating takes a name and nothing else — the rest of the Workflow contract
(list, rename, duplicate, delete) is the app shell's. What lives here is the
document: one GET that reads the Draft whole and one PUT that replaces it,
the publish that snapshots it into a numbered Version, the Versions that can
be listed, read, and restored but never written, and the one comparison the
publish modal and the Draft chip both read.
"""

from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.workflows import document
from step_by_step_api.workflows.document import (
    DocumentDiff,
    DraftState,
    WorkflowDocument,
)
from step_by_step_api.workflows.models import (
    NAME_LENGTH,
    Workflow,
    WorkflowDraft,
    WorkflowVersion,
)


class DocumentRoute(APIRoute):
    """A route whose body is a Workflow document, refused in this app's shape.

    FastAPI answers a body it cannot parse with its own 422 and its own
    envelope. A client of these two routes reads one `code` for every refusal
    — a duplicate id, an undeclared Variable, an unknown type — so the shape
    failure has to arrive as a code as well, and not as a second dialect.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handle = super().get_route_handler()

        async def refuse_with_a_code(request: Request) -> Response:
            try:
                return await handle(request)
            except RequestValidationError as unparsable:
                raise document.shape_refusal(list(unparsable.errors())) from None

        return refuse_with_a_code


router = APIRouter()
drafts = APIRouter(route_class=DocumentRoute)


class WorkflowCreation(BaseModel):
    """Everything creating a Workflow asks for: what to call it."""

    name: str = Field(min_length=1, max_length=NAME_LENGTH)


class WorkflowRecord(BaseModel):
    """The Workflow row itself, without its document.

    What creating one answers with. The list has a summary of its own, richer
    and joined against the Draft and the Versions; this is the plain row.
    """

    id: UUID
    name: str
    default_step_timeout_ms: int
    takeover_timeout_ms: int
    created_at: datetime


@router.post(
    "/api/workflows",
    operation_id="createWorkflow",
    status_code=201,
    responses=errors(400, 401, 403),
)
def create_workflow(
    asked: WorkflowCreation, member: ActiveMembership, db: SessionDep
) -> WorkflowRecord:
    """Make an empty Workflow in the acting Organization.

    Its Draft exists from this moment, empty: a recorder or an editor opening
    a Workflow that has never been touched must find a document to write into
    rather than a missing row.
    """
    workflow = Workflow(org_id=member.org_id, name=asked.name)
    db.add(workflow)
    db.flush()
    db.add(WorkflowDraft(workflow_id=workflow.id, document=document.empty()))
    db.commit()
    return summary(workflow)


def summary(workflow: Workflow) -> WorkflowRecord:
    """The Workflow as every route that answers with one renders it."""
    return WorkflowRecord(
        id=workflow.id,
        name=workflow.name,
        default_step_timeout_ms=workflow.default_step_timeout_ms,
        takeover_timeout_ms=workflow.takeover_timeout_ms,
        created_at=workflow.created_at,
    )


def draft_of(
    db: SessionDep,
    member: ActiveMembership,
    workflow_id: UUID,
    *,
    locked: bool = False,
) -> WorkflowDraft:
    """The Draft of a Workflow the acting Organization owns.

    Owned by somebody else, or not there at all, answer the same: another
    Organization's Workflow is missing, not forbidden. A 403 would confirm
    that the id exists, which is a question only its owner may ask.

    `locked` holds the row until the request commits, which is what makes the
    next Version number the next one: two publishes that read the same count
    would otherwise both mint it, and the one that lost would be the user's
    work disappearing behind a database error.
    """
    reading = (
        select(WorkflowDraft)
        .join(Workflow, Workflow.id == WorkflowDraft.workflow_id)
        .where(Workflow.id == workflow_id, Workflow.org_id == member.org_id)
    )
    draft = db.execute(
        reading.with_for_update(of=WorkflowDraft) if locked else reading
    ).scalar_one_or_none()
    if draft is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return draft


@drafts.get(
    "/api/workflows/{workflow_id}/draft",
    operation_id="getWorkflowDraft",
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    responses=errors(400, 401, 403, 404),
)
def get_workflow_draft(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> WorkflowDocument:
    """The Draft as one document: its Steps and the Variables they reference."""
    return WorkflowDocument.model_validate(draft_of(db, member, workflow_id).document)


@drafts.put(
    "/api/workflows/{workflow_id}/draft",
    operation_id="saveWorkflowDraft",
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    responses=errors(400, 401, 403, 404),
)
def save_workflow_draft(
    workflow_id: UUID, saved: WorkflowDocument, member: ActiveMembership, db: SessionDep
) -> WorkflowDocument:
    """Replace the Draft with the document sent, whole.

    Whole rather than patched: the editor holds the document it is editing, so
    a save is a statement of what the Draft now is, and there is no order of
    arrival in which two saves leave a Draft nobody wrote.
    """
    draft = draft_of(db, member, workflow_id)
    draft.document = document.stored(document.validated(saved))
    db.commit()
    return saved


class VersionSummary(BaseModel):
    """A Version without its document — what a version dropdown lists."""

    number: int
    created_at: datetime


@router.post(
    "/api/workflows/{workflow_id}/versions",
    operation_id="publishWorkflowVersion",
    status_code=201,
    responses=errors(400, 401, 403, 404),
)
def publish_workflow_version(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> VersionSummary:
    """Snapshot the Draft as the next Version.

    The document is copied across as it is stored rather than re-serialized
    through the models: what a Run reads weeks from now has to be what the
    editor was looking at, down to the byte, and a round trip through code
    that has changed since is exactly how that stops being true.
    """
    draft = draft_of(db, member, workflow_id, locked=True)
    published = WorkflowVersion(
        workflow_id=workflow_id,
        number=next_number(db, workflow_id),
        document=draft.document,
    )
    db.add(published)
    db.commit()
    return VersionSummary(number=published.number, created_at=published.created_at)


def next_number(db: SessionDep, workflow_id: UUID) -> int:
    """The number this Workflow's next Version carries. The first one is 1."""
    highest = db.execute(
        select(func.max(WorkflowVersion.number)).where(
            WorkflowVersion.workflow_id == workflow_id
        )
    ).scalar_one()
    return (highest or 0) + 1


@router.get(
    "/api/workflows/{workflow_id}/versions",
    operation_id="listWorkflowVersions",
    responses=errors(400, 401, 403, 404),
)
def list_workflow_versions(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> list[VersionSummary]:
    """Every Version of this Workflow, oldest first, without their documents."""
    draft_of(db, member, workflow_id)
    published = db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number)
    ).scalars()
    return [
        VersionSummary(number=version.number, created_at=version.created_at)
        for version in published
    ]


def version_of(
    db: SessionDep, member: ActiveMembership, workflow_id: UUID, number: int
) -> WorkflowVersion:
    """One Version of a Workflow the acting Organization owns."""
    draft_of(db, member, workflow_id)
    published = db.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.number == number,
        )
    ).scalar_one_or_none()
    if published is None:
        raise ApiError(404, "version_not_found", f"this Workflow has no v{number}")
    return published


@router.get(
    "/api/workflows/{workflow_id}/versions/{number}",
    operation_id="getWorkflowVersion",
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    responses=errors(400, 401, 403, 404),
)
def get_workflow_version(
    workflow_id: UUID, number: int, member: ActiveMembership, db: SessionDep
) -> WorkflowDocument:
    """One published document, exactly as the publish that minted it left it."""
    return WorkflowDocument.model_validate(
        version_of(db, member, workflow_id, number).document
    )


@router.post(
    "/api/workflows/{workflow_id}/versions/{number}/restore",
    operation_id="restoreWorkflowVersion",
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    responses=errors(400, 401, 403, 404),
)
def restore_workflow_version(
    workflow_id: UUID, number: int, member: ActiveMembership, db: SessionDep
) -> WorkflowDocument:
    """Copy a Version's document back into the Draft.

    An edit of the Draft and nothing more: the Version stays where it is, and
    what Schedules and Batches execute does not change until the user
    publishes what they restored.

    The document is not revalidated on the way in. It passed the rules at the
    save that preceded its publish, and a Version is executable forever —
    refusing to bring one back because a rule has since grown stricter would
    make it exactly not that.
    """
    published = version_of(db, member, workflow_id, number)
    draft_of(db, member, workflow_id).document = published.document
    db.commit()
    return WorkflowDocument.model_validate(published.document)


class DraftComparison(DocumentDiff):
    """The Draft measured against the latest Version.

    One answer for two readers: the publish modal renders the three lists, and
    the Draft chip in the editor header — and the same chip in the Workflows
    list — renders the state. They are one derivation because they are one
    question, and two answers could disagree.
    """

    state: DraftState
    latest_version: int | None
    """The number the Draft is compared against, absent until a first publish."""


@router.get(
    "/api/workflows/{workflow_id}/draft/diff",
    operation_id="getWorkflowDraftDiff",
    responses=errors(400, 401, 403, 404),
)
def get_workflow_draft_diff(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> DraftComparison:
    """What publishing would change, and where the Draft stands.

    Against the latest Version and no other: it is what Schedules and Batches
    execute, so it is the only thing "unpublished changes" can mean.
    """
    draft = draft_of(db, member, workflow_id)
    latest = latest_version(db, workflow_id)
    published = latest.document if latest is not None else document.empty()
    changes = document.diff(
        WorkflowDocument.model_validate(published),
        WorkflowDocument.model_validate(draft.document),
    )
    return DraftComparison(
        added=changes.added,
        changed=changes.changed,
        removed=changes.removed,
        state=document.draft_state(
            draft.document, latest.document if latest is not None else None
        ),
        latest_version=latest.number if latest is not None else None,
    )


def latest_version(db: SessionDep, workflow_id: UUID) -> WorkflowVersion | None:
    """The newest Version of this Workflow, or nothing if it has never been
    published — which is the difference between two of the three draft states."""
    return db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()


router.include_router(drafts)
