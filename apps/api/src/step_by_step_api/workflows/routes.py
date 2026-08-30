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
from step_by_step_api.schedules.models import Schedule
from step_by_step_api.schedules.routes import missing_from, public_variable_names
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
    name: str = Field(min_length=1, max_length=NAME_LENGTH)


class WorkflowRecord(BaseModel):
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
    workflow = Workflow(org_id=member.org_id, name=asked.name)
    db.add(workflow)
    db.flush()
    db.add(WorkflowDraft(workflow_id=workflow.id, document=document.empty()))
    db.commit()
    return summary(workflow)


def summary(workflow: Workflow) -> WorkflowRecord:
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
    draft = draft_of(db, member, workflow_id)
    draft.document = document.stored(document.validated(saved))
    db.commit()
    return saved


class VersionSummary(BaseModel):
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
    published = version_of(db, member, workflow_id, number)
    draft_of(db, member, workflow_id).document = published.document
    db.commit()
    return WorkflowDocument.model_validate(published.document)


class StrandedScheduleRef(BaseModel):
    id: UUID
    name: str | None
    cron: str


class DraftComparison(DocumentDiff):
    state: DraftState
    latest_version: int | None
    stranded_schedules: list[StrandedScheduleRef]


@router.get(
    "/api/workflows/{workflow_id}/draft/diff",
    operation_id="getWorkflowDraftDiff",
    responses=errors(400, 401, 403, 404),
)
def get_workflow_draft_diff(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> DraftComparison:
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
        stranded_schedules=stranded_by(db, workflow_id, draft.document),
    )


def stranded_by(
    db: SessionDep, workflow_id: UUID, candidate: dict[str, Any]
) -> list[StrandedScheduleRef]:
    names = public_variable_names(candidate)
    rows = db.execute(
        select(Schedule)
        .where(Schedule.workflow_id == workflow_id, Schedule.enabled.is_(True))
        .order_by(Schedule.created_at, Schedule.id)
    ).scalars()
    return [
        StrandedScheduleRef(id=row.id, name=row.name, cron=row.cron)
        for row in rows
        if missing_from(row.variables, names)
    ]


def latest_version(db: SessionDep, workflow_id: UUID) -> WorkflowVersion | None:
    return db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()


router.include_router(drafts)
