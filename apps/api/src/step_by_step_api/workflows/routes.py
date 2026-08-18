"""The Workflow HTTP surface: create a Workflow, read and save its Draft.

Creating takes a name and nothing else — the rest of the Workflow contract
(list, rename, duplicate, delete) is the app shell's. What lives here is the
document: one GET that reads the Draft whole, and one PUT that replaces it.
"""

from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from sqlalchemy import select

from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.workflows import document
from step_by_step_api.workflows.document import WorkflowDocument
from step_by_step_api.workflows.models import NAME_LENGTH, Workflow, WorkflowDraft


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


class WorkflowSummary(BaseModel):
    """A Workflow without its document — what a screen shows before opening it."""

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
) -> WorkflowSummary:
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


def summary(workflow: Workflow) -> WorkflowSummary:
    """The Workflow as every route that answers with one renders it."""
    return WorkflowSummary(
        id=workflow.id,
        name=workflow.name,
        default_step_timeout_ms=workflow.default_step_timeout_ms,
        takeover_timeout_ms=workflow.takeover_timeout_ms,
        created_at=workflow.created_at,
    )


def draft_of(
    db: SessionDep, member: ActiveMembership, workflow_id: UUID
) -> WorkflowDraft:
    """The Draft of a Workflow the acting Organization owns.

    Owned by somebody else, or not there at all, answer the same: another
    Organization's Workflow is missing, not forbidden. A 403 would confirm
    that the id exists, which is a question only its owner may ask.
    """
    draft = db.execute(
        select(WorkflowDraft)
        .join(Workflow, Workflow.id == WorkflowDraft.workflow_id)
        .where(Workflow.id == workflow_id, Workflow.org_id == member.org_id)
    ).scalar_one_or_none()
    if draft is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return draft


@drafts.get(
    "/api/workflows/{workflow_id}/draft",
    operation_id="getWorkflowDraft",
    response_model_exclude_none=True,
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


router.include_router(drafts)
