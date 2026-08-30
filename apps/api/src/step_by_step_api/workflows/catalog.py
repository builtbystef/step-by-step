import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, Select, func, literal, select, true, tuple_
from sqlalchemy.orm import InstrumentedAttribute, Session
from step_by_step_core.objects import artifact_bucket, object_store

from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.runs.models import NON_TERMINAL, Artifact, Run, RunStatus
from step_by_step_api.schedules.models import Schedule
from step_by_step_api.workflows import document
from step_by_step_api.workflows.document import DraftState
from step_by_step_api.workflows.models import (
    NAME_LENGTH,
    Workflow,
    WorkflowDraft,
    WorkflowVersion,
)

router = APIRouter()


class WorkflowSort(StrEnum):
    ACTIVITY = "activity"
    NAME = "name"
    CREATED = "created"


class LastRun(BaseModel):
    id: UUID
    status: RunStatus
    finished_at: datetime | None


class WorkflowSummary(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    last_activity_at: datetime
    draft_state: DraftState
    published_version: int | None = None
    default_step_timeout_ms: int
    last_run: LastRun | None = None
    schedule_count: int
    schedule_label: str | None = None
    recent_run_median_ms: int | None = None
    run_count: int


class WorkflowPage(BaseModel):
    items: list[WorkflowSummary]
    next_cursor: str | None = None


PAGE_SIZE = 25

MAX_PAGE_SIZE = 100


@router.get(
    "/api/workflows",
    operation_id="listWorkflows",
    response_model_exclude_none=True,
    responses=errors(400, 401, 403),
)
def list_workflows(
    member: ActiveMembership,
    db: SessionDep,
    q: Annotated[str, Query(max_length=NAME_LENGTH)] = "",
    sort: WorkflowSort = WorkflowSort.ACTIVITY,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = PAGE_SIZE,
    cursor: str | None = None,
) -> WorkflowPage:
    page = catalogue(member, q, sort).where(*after(cursor, sort)).limit(limit + 1)
    rows = list(db.execute(page))
    return WorkflowPage(
        items=summarise(db, rows[:limit]),
        next_cursor=cut(rows[limit - 1], sort) if len(rows) > limit else None,
    )


def cut(row: Any, sort: WorkflowSort) -> str:
    return urlsafe_b64encode(
        json.dumps(
            {"s": sort.value, "k": key_of(row, sort), "i": str(row.Workflow.id)}
        ).encode()
    ).decode()


def key_of(row: Any, sort: WorkflowSort) -> str:
    if sort is WorkflowSort.NAME:
        return row.Workflow.name
    if sort is WorkflowSort.CREATED:
        return row.Workflow.created_at.isoformat()
    return row.last_activity_at.isoformat()


def after(cursor: str | None, sort: WorkflowSort) -> list[ColumnElement[bool]]:
    if cursor is None:
        return []
    key, last = read(cursor, sort)
    place = tuple_(sort_key(sort), Workflow.id)
    behind = tuple_(literal(key), literal(last))
    return [place > behind if ascending(sort) else place < behind]


def read(cursor: str, sort: WorkflowSort) -> tuple[str | datetime, UUID]:
    try:
        cut_at = json.loads(urlsafe_b64decode(cursor.encode()))
        if cut_at["s"] != sort.value:
            raise ValueError(cut_at["s"])
        key = cut_at["k"]
        return (
            key if sort is WorkflowSort.NAME else datetime.fromisoformat(key)
        ), UUID(cut_at["i"])
    except Exception:
        raise ApiError(
            400, "bad_cursor", "that cursor did not come from this list, in this order"
        ) from None


def activity() -> ColumnElement[datetime]:
    latest_run_at = (
        select(func.max(Run.queued_at))
        .where(Run.workflow_id == Workflow.id)
        .correlate(Workflow)
        .scalar_subquery()
    )
    return func.greatest(
        Workflow.updated_at,
        WorkflowDraft.updated_at,
        func.coalesce(latest_run_at, Workflow.updated_at),
    )


def catalogue(member: ActiveMembership, q: str, sort: WorkflowSort) -> Select[Any]:
    latest = (
        select(WorkflowVersion.number, WorkflowVersion.document)
        .where(WorkflowVersion.workflow_id == Workflow.id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
        .lateral("latest")
    )
    return (
        select(
            Workflow,
            activity().label("last_activity_at"),
            latest.c.number.label("published_version"),
            (latest.c.document == WorkflowDraft.document).label("matches_published"),
        )
        .join(WorkflowDraft, WorkflowDraft.workflow_id == Workflow.id)
        .outerjoin(latest, true())
        .where(Workflow.org_id == member.org_id, *matching(q))
        .order_by(*ordering(sort))
    )


SortKey = ColumnElement[Any] | InstrumentedAttribute[Any]


def sort_key(sort: WorkflowSort) -> SortKey:
    if sort is WorkflowSort.NAME:
        return Workflow.name
    if sort is WorkflowSort.CREATED:
        return Workflow.created_at
    return activity()


def ascending(sort: WorkflowSort) -> bool:
    return sort is WorkflowSort.NAME


def ordering(sort: WorkflowSort) -> list[ColumnElement[Any]]:
    key, tiebreak = sort_key(sort), Workflow.id
    if ascending(sort):
        return [key.asc(), tiebreak.asc()]
    return [key.desc(), tiebreak.desc()]


def matching(q: str) -> list[ColumnElement[bool]]:
    if q == "":
        return []
    wanted = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return [Workflow.name.ilike(f"%{wanted}%", escape="\\")]


def summarise(db: Session, rows: list[Any]) -> list[WorkflowSummary]:
    ids = [row.Workflow.id for row in rows]
    last_runs = last_runs_of(db, ids)
    schedules = schedules_of(db, ids)
    run_counts = run_counts_of(db, ids)
    medians = medians_of(db, ids)
    return [
        summary(
            row,
            last_run=last_runs.get(row.Workflow.id),
            schedule_count=schedules.get(row.Workflow.id, (0, None))[0],
            schedule_cron=schedules.get(row.Workflow.id, (0, None))[1],
            run_count=run_counts.get(row.Workflow.id, 0),
            recent_run_median_ms=medians.get(row.Workflow.id),
        )
        for row in rows
    ]


def summary(
    row: Any,
    *,
    last_run: LastRun | None,
    schedule_count: int,
    schedule_cron: str | None,
    run_count: int,
    recent_run_median_ms: int | None,
) -> WorkflowSummary:
    workflow: Workflow = row.Workflow
    return WorkflowSummary(
        id=workflow.id,
        name=workflow.name,
        created_at=workflow.created_at,
        last_activity_at=row.last_activity_at,
        draft_state=document.standing(
            row.published_version is not None, row.matches_published is True
        ),
        published_version=row.published_version,
        default_step_timeout_ms=workflow.default_step_timeout_ms,
        last_run=last_run,
        schedule_count=schedule_count,
        schedule_label=(
            compact_schedule(schedule_cron)
            if schedule_count == 1 and schedule_cron is not None
            else None
        ),
        recent_run_median_ms=recent_run_median_ms,
        run_count=run_count,
    )


def last_runs_of(db: Session, ids: list[UUID]) -> dict[UUID, LastRun]:
    if not ids:
        return {}
    rows = db.execute(
        select(Run)
        .distinct(Run.workflow_id)
        .where(Run.workflow_id.in_(ids))
        .order_by(Run.workflow_id, Run.queued_at.desc(), Run.id.desc())
    ).scalars()
    return {
        run.workflow_id: LastRun(id=run.id, status=run.status, finished_at=run.ended_at)
        for run in rows
    }


def schedules_of(db: Session, ids: list[UUID]) -> dict[UUID, tuple[int, str | None]]:
    if not ids:
        return {}
    rows = db.execute(
        select(Schedule.workflow_id, func.count(), func.min(Schedule.cron))
        .where(Schedule.workflow_id.in_(ids))
        .group_by(Schedule.workflow_id)
    )
    return {
        workflow_id: (count, cron if count == 1 else None)
        for workflow_id, count, cron in rows
    }


def run_counts_of(db: Session, ids: list[UUID]) -> dict[UUID, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(Run.workflow_id, func.count())
        .where(Run.workflow_id.in_(ids))
        .group_by(Run.workflow_id)
    )
    return {workflow_id: count for workflow_id, count in rows}


def medians_of(db: Session, ids: list[UUID]) -> dict[UUID, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(Run.workflow_id, Run.started_at, Run.queued_at, Run.ended_at)
        .where(
            Run.workflow_id.in_(ids),
            Run.status == RunStatus.SUCCEEDED,
            Run.ended_at.is_not(None),
        )
        .order_by(Run.workflow_id, Run.queued_at.desc())
    )
    samples: dict[UUID, list[int]] = {}
    for workflow_id, started, queued, ended in rows:
        assert ended is not None
        bucket = samples.setdefault(workflow_id, [])
        if len(bucket) < 10:
            start = started or queued
            bucket.append(int((ended - start).total_seconds() * 1000))
    return {
        workflow_id: int(median(durations))
        for workflow_id, durations in samples.items()
        if len(durations) >= 3
    }


def median(values: list[int]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


WEEKDAY_NAMES = (
    "Sundays",
    "Mondays",
    "Tuesdays",
    "Wednesdays",
    "Thursdays",
    "Fridays",
    "Saturdays",
)


def compact_schedule(cron: str) -> str:
    fields = cron.split()
    if len(fields) != 5:
        return cron
    minute, hour, day, month, weekday = fields
    if month != "*":
        return cron
    if minute.startswith("*/") and hour == day == weekday == "*":
        step = minute[2:]
        if step.isdigit() and 1 <= int(step) <= 59:
            return f"every {int(step)} min"
        return cron
    clock = clock_of(hour, minute)
    if hour == day == weekday == "*" and minute.isdigit() and 0 <= int(minute) <= 59:
        return "hourly" if int(minute) == 0 else f"hourly :{int(minute):02d}"
    if clock is None:
        return cron
    if day == weekday == "*":
        return f"daily {clock}"
    if day == "*" and weekday == "1-5":
        return f"weekdays {clock}"
    if day == "*" and _distinct_weekdays(weekday):
        names = [WEEKDAY_NAMES[int(part)] for part in weekday.split(",")]
        if len(names) == 1:
            return f"{names[0]} {clock}"
        return f"{', '.join(names[:-1])} and {names[-1]} {clock}"
    if weekday == "*" and day.isdigit() and 1 <= int(day) <= 31:
        return f"day {int(day)} {clock}"
    return cron


def clock_of(hour: str, minute: str) -> str | None:
    if hour.isdigit() and minute.isdigit():
        hours, minutes = int(hour), int(minute)
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
    return None


def _distinct_weekdays(field: str) -> bool:
    parts = field.split(",")
    return (
        bool(parts)
        and len(parts) == len(set(parts))
        and all(part.isdigit() and 0 <= int(part) <= 6 for part in parts)
    )


@router.get(
    "/api/workflows/{workflow_id}",
    operation_id="getWorkflow",
    response_model_exclude_none=True,
    responses=errors(400, 401, 403, 404),
)
def get_workflow(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> WorkflowSummary:
    row = db.execute(
        catalogue(member, "", WorkflowSort.ACTIVITY).where(Workflow.id == workflow_id)
    ).first()
    if row is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return summarise(db, [row])[0]


class WorkflowRename(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_LENGTH)


class WorkflowNamed(BaseModel):
    id: UUID
    name: str


@router.patch(
    "/api/workflows/{workflow_id}",
    operation_id="renameWorkflow",
    responses=errors(400, 401, 403, 404),
)
def rename_workflow(
    workflow_id: UUID, asked: WorkflowRename, member: ActiveMembership, db: SessionDep
) -> WorkflowNamed:
    workflow = owned(db, member, workflow_id)
    workflow.name = asked.name
    db.commit()
    return WorkflowNamed(id=workflow.id, name=workflow.name)


def owned(db: SessionDep, member: ActiveMembership, workflow_id: UUID) -> Workflow:
    workflow = db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.org_id == member.org_id
        )
    ).scalar_one_or_none()
    if workflow is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return workflow


COPY_SUFFIX = " (copy)"


@router.post(
    "/api/workflows/{workflow_id}/duplicate",
    operation_id="duplicateWorkflow",
    status_code=201,
    responses=errors(400, 401, 403, 404),
)
def duplicate_workflow(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> WorkflowNamed:
    source = owned(db, member, workflow_id)
    draft = db.execute(
        select(WorkflowDraft).where(WorkflowDraft.workflow_id == source.id)
    ).scalar_one()
    copy = Workflow(
        org_id=source.org_id,
        name=named_as_a_copy(source.name),
        default_step_timeout_ms=source.default_step_timeout_ms,
        takeover_timeout_ms=source.takeover_timeout_ms,
    )
    db.add(copy)
    db.flush()
    db.add(
        WorkflowDraft(
            workflow_id=copy.id,
            document=document.with_fresh_step_ids(draft.document),
        )
    )
    db.commit()
    return WorkflowNamed(id=copy.id, name=copy.name)


def named_as_a_copy(name: str) -> str:
    return name[: NAME_LENGTH - len(COPY_SUFFIX)] + COPY_SUFFIX


@router.delete(
    "/api/workflows/{workflow_id}",
    operation_id="deleteWorkflow",
    status_code=204,
    responses=errors(400, 401, 403, 404, 409),
)
def delete_workflow(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> Response:
    workflow = owned(db, member, workflow_id)
    live = db.scalar(
        select(func.count())
        .select_from(Run)
        .where(Run.workflow_id == workflow.id, Run.status.in_(NON_TERMINAL))
    )
    if live:
        raise ApiError(
            409, "run_active", "this Workflow has a Run that is still active"
        )
    keys = list(
        db.execute(
            select(Artifact.object_key)
            .join(Run, Artifact.run_id == Run.id)
            .where(Run.workflow_id == workflow.id)
        )
        .scalars()
        .all()
    )
    bucket = artifact_bucket()
    store = object_store()
    for key in keys:
        store.delete_object(Bucket=bucket, Key=key)
    db.delete(workflow)
    db.commit()
    return Response(status_code=204)
