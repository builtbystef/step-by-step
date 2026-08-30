import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import literal, select, tuple_
from sqlalchemy.orm import Session
from step_by_step_core.bus import DISPATCH_LIST, get_redis

from step_by_step_api import clock
from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.runs.models import FailureReason, Run, RunStatus
from step_by_step_api.schedules.cron import (
    PREVIEW_COUNT,
    next_occurrence,
    next_occurrences,
    require_cron,
    require_timezone,
)
from step_by_step_api.schedules.fire import enqueue_latest, open_run_id
from step_by_step_api.schedules.models import Schedule, ScheduleOccurrence
from step_by_step_api.workflows.models import Workflow, WorkflowVersion

router = APIRouter(tags=["schedules"])
PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class CreateSchedule(BaseModel):
    cron: str
    timezone: str
    enabled: bool
    variables: dict[str, Any] = Field(default_factory=dict)
    name: str | None = None


class ChangeSchedule(BaseModel):
    cron: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    variables: dict[str, Any] | None = None
    name: str | None = None


class PreviewRequest(BaseModel):
    cron: str
    timezone: str
    from_: datetime | None = Field(default=None, alias="from")


class PreviewResult(BaseModel):
    next_occurrences: list[datetime]


class OccurrenceRecord(BaseModel):
    occurrence_at: datetime
    reason: Literal["overlap", "missed", "missing_values"]
    blocking_run_id: UUID | None = None


class LastRunRecord(BaseModel):
    id: UUID
    status: RunStatus
    failure_reason: FailureReason | None = None
    ended_at: datetime | None = None


class ScheduleSummary(BaseModel):
    id: UUID
    workflow_id: UUID
    workflow_name: str
    name: str | None
    cron: str
    timezone: str
    enabled: bool
    variables: dict[str, Any]
    state: Literal["active", "paused", "needs_values"]
    missing_variable_names: list[str]
    last_fired_at: datetime | None
    next_due_at: datetime | None
    last_run: LastRunRecord | None
    latest_occurrence: OccurrenceRecord | None


class SchedulePage(BaseModel):
    items: list[ScheduleSummary]
    next_cursor: str | None = None


class RunHistoryEntry(BaseModel):
    kind: Literal["run"] = "run"
    at: datetime
    run_id: UUID
    status: RunStatus
    failure_reason: FailureReason | None = None


class OccurrenceHistoryEntry(BaseModel):
    kind: Literal["occurrence"] = "occurrence"
    at: datetime
    reason: Literal["overlap", "missed", "missing_values"]
    blocking_run_id: UUID | None = None


class ScheduleDetail(BaseModel):
    schedule: ScheduleSummary
    next_occurrences: list[datetime]
    history: list[RunHistoryEntry | OccurrenceHistoryEntry]
    last_run: LastRunRecord | None


class RunNowResult(BaseModel):
    run_id: UUID


def owned_workflow(db: SessionDep, org_id: UUID, workflow_id: UUID) -> Workflow:
    found = db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.org_id == org_id)
    ).scalar_one_or_none()
    if found is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return found


def owned_schedule(db: SessionDep, org_id: UUID, schedule_id: UUID) -> Schedule:
    found = db.execute(
        select(Schedule).where(Schedule.id == schedule_id, Schedule.org_id == org_id)
    ).scalar_one_or_none()
    if found is None:
        raise ApiError(404, "schedule_not_found", "no such Schedule")
    return found


def latest_published(db: Session, workflow_id: UUID) -> WorkflowVersion | None:
    return db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()


def public_variable_names(document: dict[str, Any]) -> set[str]:
    return {
        variable["name"]
        for variable in document.get("variables", [])
        if not variable.get("secret", False)
    }


def stored_variables(asked: dict[str, Any], names: set[str]) -> dict[str, Any]:
    return {name: value for name, value in asked.items() if name in names}


def missing_from(values: dict[str, Any], names: set[str]) -> list[str]:
    return sorted(name for name in names if name not in values)


def require_variable_values(asked: dict[str, Any], names: set[str]) -> dict[str, Any]:
    missing = missing_from(asked, names)
    if missing:
        raise ApiError(
            400,
            "missing_variable_values",
            "every non-secret Variable needs a value",
            variable_names=missing,
        )
    return stored_variables(asked, names)


def declared_public_names(db: Session, workflow_id: UUID) -> set[str]:
    published = latest_published(db, workflow_id)
    if published is None:
        return set()
    return public_variable_names(published.document)


def derived_state(
    enabled: bool, missing: list[str]
) -> Literal["active", "paused", "needs_values"]:
    if not enabled:
        return "paused"
    if missing:
        return "needs_values"
    return "active"


def latest_hole(db: Session, schedule_id: UUID) -> OccurrenceRecord | None:
    found = db.execute(
        select(ScheduleOccurrence)
        .where(ScheduleOccurrence.schedule_id == schedule_id)
        .order_by(ScheduleOccurrence.occurrence_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if found is None:
        return None
    return OccurrenceRecord(
        occurrence_at=found.occurrence_at,
        reason=found.reason.value,
        blocking_run_id=found.blocking_run_id,
    )


def last_run_of(db: Session, schedule_id: UUID) -> LastRunRecord | None:
    found = db.execute(
        select(Run)
        .where(Run.schedule_id == schedule_id)
        .order_by(Run.queued_at.desc(), Run.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if found is None:
        return None
    return LastRunRecord(
        id=found.id,
        status=found.status,
        failure_reason=found.failure_reason,
        ended_at=found.ended_at,
    )


def as_summary(db: Session, schedule: Schedule, names: set[str]) -> ScheduleSummary:
    workflow = db.execute(
        select(Workflow).where(Workflow.id == schedule.workflow_id)
    ).scalar_one()
    missing = missing_from(schedule.variables, names)
    return ScheduleSummary(
        id=schedule.id,
        workflow_id=schedule.workflow_id,
        workflow_name=workflow.name,
        name=schedule.name,
        cron=schedule.cron,
        timezone=schedule.timezone,
        enabled=schedule.enabled,
        variables=schedule.variables,
        state=derived_state(schedule.enabled, missing),
        missing_variable_names=missing,
        last_fired_at=schedule.last_fired_at,
        next_due_at=schedule.next_due_at,
        last_run=last_run_of(db, schedule.id),
        latest_occurrence=latest_hole(db, schedule.id),
    )


def summaries_of(db: Session, rows: list[Schedule]) -> list[ScheduleSummary]:
    return [
        as_summary(db, row, declared_public_names(db, row.workflow_id)) for row in rows
    ]


def cursor_for(schedule: Schedule) -> str:
    return urlsafe_b64encode(
        json.dumps(
            {"at": schedule.created_at.isoformat(), "id": str(schedule.id)}
        ).encode()
    ).decode()


def read_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        payload = json.loads(urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(payload["at"]), UUID(payload["id"])
    except Exception:
        raise ApiError(
            400, "bad_cursor", "that cursor did not come from this list"
        ) from None


def history_of(
    db: Session, schedule_id: UUID
) -> list[RunHistoryEntry | OccurrenceHistoryEntry]:
    runs = db.execute(
        select(Run)
        .where(Run.schedule_id == schedule_id)
        .order_by(Run.queued_at, Run.id)
    ).scalars()
    holes = db.execute(
        select(ScheduleOccurrence)
        .where(ScheduleOccurrence.schedule_id == schedule_id)
        .order_by(ScheduleOccurrence.occurrence_at, ScheduleOccurrence.id)
    ).scalars()
    entries: list[RunHistoryEntry | OccurrenceHistoryEntry] = [
        RunHistoryEntry(
            at=run.queued_at,
            run_id=run.id,
            status=run.status,
            failure_reason=run.failure_reason,
        )
        for run in runs
    ]
    entries.extend(
        OccurrenceHistoryEntry(
            at=hole.occurrence_at,
            reason=hole.reason.value,
            blocking_run_id=hole.blocking_run_id,
        )
        for hole in holes
    )
    entries.sort(key=lambda entry: (entry.at, entry.kind))
    return entries


@router.post(
    "/api/schedules/preview",
    operation_id="previewSchedule",
    responses=errors(400, 401, 403),
)
def preview_schedule(asked: PreviewRequest, member: ActiveMembership) -> PreviewResult:
    after = asked.from_ if asked.from_ is not None else clock.now()
    return PreviewResult(
        next_occurrences=next_occurrences(
            asked.cron, asked.timezone, after, count=PREVIEW_COUNT
        )
    )


@router.get(
    "/api/schedules",
    operation_id="listAllSchedules",
    responses=errors(400, 401, 403, 404),
)
def list_all_schedules(
    member: ActiveMembership,
    db: SessionDep,
    workflow_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = PAGE_SIZE,
    cursor: str | None = None,
) -> SchedulePage:
    conditions = [Schedule.org_id == member.org_id]
    if workflow_id is not None:
        owned_workflow(db, member.org_id, workflow_id)
        conditions.append(Schedule.workflow_id == workflow_id)
    if cursor is not None:
        created_at, schedule_id = read_cursor(cursor)
        conditions.append(
            tuple_(Schedule.created_at, Schedule.id)
            > tuple_(literal(created_at), literal(schedule_id))
        )
    rows = list(
        db.execute(
            select(Schedule)
            .where(*conditions)
            .order_by(Schedule.created_at, Schedule.id)
            .limit(limit + 1)
        ).scalars()
    )
    return SchedulePage(
        items=summaries_of(db, rows[:limit]),
        next_cursor=cursor_for(rows[limit - 1]) if len(rows) > limit else None,
    )


@router.get(
    "/api/workflows/{workflow_id}/schedules",
    operation_id="listSchedules",
    responses=errors(400, 401, 403, 404),
)
def list_schedules(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> list[ScheduleSummary]:
    owned_workflow(db, member.org_id, workflow_id)
    names = declared_public_names(db, workflow_id)
    rows = db.execute(
        select(Schedule)
        .where(Schedule.workflow_id == workflow_id, Schedule.org_id == member.org_id)
        .order_by(Schedule.created_at, Schedule.id)
    ).scalars()
    return [as_summary(db, row, names) for row in rows]


@router.post(
    "/api/workflows/{workflow_id}/schedules",
    operation_id="createSchedule",
    status_code=201,
    responses=errors(400, 401, 403, 404, 409),
)
def create_schedule(
    workflow_id: UUID,
    asked: CreateSchedule,
    member: ActiveMembership,
    db: SessionDep,
) -> ScheduleSummary:
    owned_workflow(db, member.org_id, workflow_id)
    require_cron(asked.cron)
    require_timezone(asked.timezone)
    published = latest_published(db, workflow_id)
    if published is None:
        raise ApiError(
            409,
            "no_published_version",
            "Publish a Version before this Workflow can be scheduled.",
        )
    names = public_variable_names(published.document)
    schedule = Schedule(
        org_id=member.org_id,
        workflow_id=workflow_id,
        name=asked.name,
        cron=asked.cron,
        timezone=asked.timezone,
        enabled=asked.enabled,
        variables=require_variable_values(asked.variables, names),
        next_due_at=(
            next_occurrence(asked.cron, asked.timezone, clock.now())
            if asked.enabled
            else None
        ),
    )
    db.add(schedule)
    db.commit()
    return as_summary(db, schedule, names)


@router.get(
    "/api/schedules/{schedule_id}",
    operation_id="getSchedule",
    responses=errors(400, 401, 403, 404),
)
def get_schedule(
    schedule_id: UUID, member: ActiveMembership, db: SessionDep
) -> ScheduleDetail:
    schedule = owned_schedule(db, member.org_id, schedule_id)
    names = declared_public_names(db, schedule.workflow_id)
    summary = as_summary(db, schedule, names)
    return ScheduleDetail(
        schedule=summary,
        next_occurrences=next_occurrences(
            schedule.cron, schedule.timezone, clock.now(), count=PREVIEW_COUNT
        ),
        history=history_of(db, schedule.id),
        last_run=summary.last_run,
    )


@router.patch(
    "/api/schedules/{schedule_id}",
    operation_id="updateSchedule",
    responses=errors(400, 401, 403, 404),
)
def update_schedule(
    schedule_id: UUID,
    asked: ChangeSchedule,
    member: ActiveMembership,
    db: SessionDep,
) -> ScheduleSummary:
    schedule = owned_schedule(db, member.org_id, schedule_id)
    names = declared_public_names(db, schedule.workflow_id)
    if asked.cron is not None:
        require_cron(asked.cron)
        schedule.cron = asked.cron
    if asked.timezone is not None:
        require_timezone(asked.timezone)
        schedule.timezone = asked.timezone
    turning_on = asked.enabled is True and not schedule.enabled
    turning_off = asked.enabled is False and schedule.enabled
    if asked.enabled is not None:
        schedule.enabled = asked.enabled
    if asked.variables is not None:
        schedule.variables = require_variable_values(asked.variables, names)
    if "name" in asked.model_fields_set:
        schedule.name = asked.name
    if turning_off:
        schedule.next_due_at = None
    elif schedule.enabled and (
        asked.cron is not None or asked.timezone is not None or turning_on
    ):
        schedule.next_due_at = next_occurrence(
            schedule.cron, schedule.timezone, clock.now()
        )
    db.commit()
    return as_summary(db, schedule, names)


@router.post(
    "/api/schedules/{schedule_id}/run-now",
    operation_id="runScheduleNow",
    status_code=201,
    responses=errors(400, 401, 403, 404, 409),
)
def run_schedule_now(
    schedule_id: UUID, member: ActiveMembership, db: SessionDep
) -> RunNowResult:
    schedule = owned_schedule(db, member.org_id, schedule_id)
    names = declared_public_names(db, schedule.workflow_id)
    missing = missing_from(schedule.variables, names)
    if missing:
        raise ApiError(
            409,
            "needs_values",
            "this Schedule is missing values for declared Variables",
            variable_names=missing,
        )
    blocking = open_run_id(db, schedule.id)
    if blocking is not None:
        raise ApiError(
            409,
            "schedule_run_active",
            "a Run of this Schedule is still in progress",
            blocking_run_id=str(blocking),
        )
    published = latest_published(db, schedule.workflow_id)
    if published is None:
        raise ApiError(
            409,
            "no_published_version",
            "Publish a Version before this Workflow can run.",
        )
    run_id = enqueue_latest(db, schedule, published, clock.now())
    db.commit()
    get_redis().lpush(DISPATCH_LIST, str(run_id))
    return RunNowResult(run_id=run_id)


@router.delete(
    "/api/schedules/{schedule_id}",
    operation_id="deleteSchedule",
    status_code=204,
    responses=errors(400, 401, 403, 404),
)
def delete_schedule(
    schedule_id: UUID, member: ActiveMembership, db: SessionDep
) -> Response:
    schedule = owned_schedule(db, member.org_id, schedule_id)
    db.delete(schedule)
    db.commit()
    return Response(status_code=204)
