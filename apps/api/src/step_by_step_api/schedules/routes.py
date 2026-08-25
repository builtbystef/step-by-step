"""The user-facing Schedule CRUD. Firing belongs to the minute loop."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from step_by_step_api.workflows.models import Workflow, WorkflowVersion

router = APIRouter(tags=["schedules"])


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


class ScheduleRecord(BaseModel):
    id: UUID
    name: str | None
    cron: str
    timezone: str
    enabled: bool
    variables: dict[str, Any]
    state: Literal["active", "paused", "needs_values"]
    missing_variable_names: list[str]
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


def latest_published(db: Session, workflow_id: UUID) -> WorkflowVersion | None:
    return db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()


def public_variable_names(document: dict[str, Any]) -> set[str]:
    """Non-secret Variable names the latest Version declares."""
    return {
        variable["name"]
        for variable in document.get("variables", [])
        if not variable.get("secret", False)
    }


def stored_variables(asked: dict[str, Any], names: set[str]) -> dict[str, Any]:
    """The value set a Schedule may keep: non-secret names only."""
    return {name: value for name, value in asked.items() if name in names}


def missing_from(values: dict[str, Any], names: set[str]) -> list[str]:
    return sorted(name for name in names if name not in values)


def require_variable_values(asked: dict[str, Any], names: set[str]) -> dict[str, Any]:
    """Refuse a value set that leaves a declared non-secret Variable blank."""
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


def as_record(schedule: Schedule, names: set[str]) -> ScheduleRecord:
    missing = missing_from(schedule.variables, names)
    return ScheduleRecord(
        id=schedule.id,
        name=schedule.name,
        cron=schedule.cron,
        timezone=schedule.timezone,
        enabled=schedule.enabled,
        variables=schedule.variables,
        state=derived_state(schedule.enabled, missing),
        missing_variable_names=missing,
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
    names = declared_public_names(db, workflow_id)
    rows = db.execute(
        select(Schedule)
        .where(Schedule.workflow_id == workflow_id, Schedule.org_id == member.org_id)
        .order_by(Schedule.created_at, Schedule.id)
    ).scalars()
    return [as_record(row, names) for row in rows]


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
) -> ScheduleRecord:
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
        next_due_at=next_occurrence(asked.cron, asked.timezone, clock.now()),
    )
    db.add(schedule)
    db.commit()
    return as_record(schedule, names)


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
    names = declared_public_names(db, schedule.workflow_id)
    if asked.cron is not None:
        require_cron(asked.cron)
        schedule.cron = asked.cron
    if asked.timezone is not None:
        require_timezone(asked.timezone)
        schedule.timezone = asked.timezone
    turning_on = asked.enabled is True and not schedule.enabled
    if asked.enabled is not None:
        schedule.enabled = asked.enabled
    if asked.variables is not None:
        schedule.variables = require_variable_values(asked.variables, names)
    if "name" in asked.model_fields_set:
        schedule.name = asked.name
    if asked.cron is not None or asked.timezone is not None or turning_on:
        schedule.next_due_at = next_occurrence(
            schedule.cron, schedule.timezone, clock.now()
        )
    db.commit()
    return as_record(schedule, names)


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
