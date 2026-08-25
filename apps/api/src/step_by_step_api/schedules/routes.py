"""The user-facing Schedule CRUD. Firing belongs to the minute loop."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import select

from step_by_step_api import clock
from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.schedules.cron import (
    next_occurrence,
    require_cron,
    require_timezone,
)
from step_by_step_api.schedules.models import Schedule
from step_by_step_api.workflows.models import Workflow

router = APIRouter(tags=["schedules"])


class CreateSchedule(BaseModel):
    cron: str
    timezone: str
    enabled: bool


class ChangeSchedule(BaseModel):
    cron: str | None = None
    timezone: str | None = None
    enabled: bool | None = None


class ScheduleRecord(BaseModel):
    id: UUID
    cron: str
    timezone: str
    enabled: bool
    last_fired_at: datetime | None
    next_due_at: datetime
    last_skip_reason: str | None


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


def as_record(schedule: Schedule) -> ScheduleRecord:
    return ScheduleRecord(
        id=schedule.id,
        cron=schedule.cron,
        timezone=schedule.timezone,
        enabled=schedule.enabled,
        last_fired_at=schedule.last_fired_at,
        next_due_at=schedule.next_due_at,
        last_skip_reason=schedule.last_skip_reason,
    )


@router.get(
    "/api/workflows/{workflow_id}/schedules",
    operation_id="listSchedules",
    responses=errors(400, 401, 403, 404),
)
def list_schedules(
    workflow_id: UUID, member: ActiveMembership, db: SessionDep
) -> list[ScheduleRecord]:
    owned_workflow(db, member.org_id, workflow_id)
    rows = db.execute(
        select(Schedule)
        .where(Schedule.workflow_id == workflow_id, Schedule.org_id == member.org_id)
        .order_by(Schedule.created_at, Schedule.id)
    ).scalars()
    return [as_record(row) for row in rows]


@router.post(
    "/api/workflows/{workflow_id}/schedules",
    operation_id="createSchedule",
    status_code=201,
    responses=errors(400, 401, 403, 404),
)
def create_schedule(
    workflow_id: UUID,
    asked: CreateSchedule,
    member: ActiveMembership,
    db: SessionDep,
) -> ScheduleRecord:
    owned_workflow(db, member.org_id, workflow_id)
    require_cron(asked.cron)
    require_timezone(asked.timezone)
    schedule = Schedule(
        org_id=member.org_id,
        workflow_id=workflow_id,
        cron=asked.cron,
        timezone=asked.timezone,
        enabled=asked.enabled,
        next_due_at=next_occurrence(asked.cron, asked.timezone, clock.now()),
    )
    db.add(schedule)
    db.commit()
    return as_record(schedule)


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
) -> ScheduleRecord:
    schedule = owned_schedule(db, member.org_id, schedule_id)
    if asked.cron is not None:
        require_cron(asked.cron)
        schedule.cron = asked.cron
    if asked.timezone is not None:
        require_timezone(asked.timezone)
        schedule.timezone = asked.timezone
    turning_on = asked.enabled is True and not schedule.enabled
    if asked.enabled is not None:
        schedule.enabled = asked.enabled
    if asked.cron is not None or asked.timezone is not None or turning_on:
        schedule.next_due_at = next_occurrence(
            schedule.cron, schedule.timezone, clock.now()
        )
    db.commit()
    return as_record(schedule)


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
