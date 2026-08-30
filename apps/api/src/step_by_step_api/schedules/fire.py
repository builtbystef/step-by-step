from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from step_by_step_api.runs.models import (
    DEFAULT_RUN_TIMEOUT_MS,
    NON_TERMINAL,
    Run,
    RunStatus,
    RunTrigger,
)
from step_by_step_api.schedules.cron import next_occurrence, occurrences_through
from step_by_step_api.schedules.models import (
    GRACE_WINDOW_SECONDS,
    OCCURRENCE_PRUNE_DEPTH,
    OccurrenceReason,
    Schedule,
    ScheduleOccurrence,
)
from step_by_step_api.workflows.models import WorkflowVersion


def fire_due_schedules(db: Session, now: datetime) -> list[UUID]:
    due = db.execute(
        select(Schedule)
        .where(Schedule.enabled.is_(True), Schedule.next_due_at <= now)
        .with_for_update()
        .order_by(Schedule.next_due_at, Schedule.id)
    ).scalars()
    run_ids: list[UUID] = []
    for schedule in due:
        fired = handle_due(db, schedule, now)
        if fired is not None:
            run_ids.append(fired)
    return run_ids


def handle_due(db: Session, schedule: Schedule, now: datetime) -> UUID | None:
    if schedule.next_due_at is None:
        return None
    due_times = occurrences_through(
        schedule.cron, schedule.timezone, schedule.next_due_at, now
    )
    if len(due_times) > OCCURRENCE_PRUNE_DEPTH:
        due_times = due_times[-OCCURRENCE_PRUNE_DEPTH:]
    if not due_times:
        schedule.next_due_at = next_occurrence(schedule.cron, schedule.timezone, now)
        return None
    published = latest_published(db, schedule.workflow_id)
    run_id: UUID | None = None
    if missing_public_values(published, schedule.variables):
        for at in due_times:
            record_hole(db, schedule, at, OccurrenceReason.MISSING_VALUES)
    else:
        late, on_time = split_by_grace(due_times, now)
        for at in late:
            record_hole(db, schedule, at, OccurrenceReason.MISSED)
        blocking = open_run_id(db, schedule.id)
        for at in on_time:
            if blocking is not None:
                record_hole(
                    db, schedule, at, OccurrenceReason.OVERLAP, blocking_run_id=blocking
                )
            elif run_id is None and published is not None:
                run_id = enqueue_latest(db, schedule, published, now)
                blocking = run_id
            else:
                record_hole(db, schedule, at, OccurrenceReason.MISSED)
    schedule.next_due_at = next_occurrence(
        schedule.cron, schedule.timezone, due_times[-1]
    )
    prune_occurrences(db, schedule.id)
    return run_id


def split_by_grace(
    due_times: list[datetime], now: datetime
) -> tuple[list[datetime], list[datetime]]:
    late: list[datetime] = []
    on_time: list[datetime] = []
    for at in due_times:
        if (now - at).total_seconds() > GRACE_WINDOW_SECONDS:
            late.append(at)
        else:
            on_time.append(at)
    return late, on_time


def missing_public_values(
    published: WorkflowVersion | None, values: dict[str, Any]
) -> bool:
    if published is None:
        return False
    needed = {
        variable["name"]
        for variable in published.document.get("variables", [])
        if not variable.get("secret", False)
    }
    return any(name not in values for name in needed)


def latest_published(db: Session, workflow_id: UUID) -> WorkflowVersion | None:
    return db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()


def open_run_id(db: Session, schedule_id: UUID) -> UUID | None:
    return db.execute(
        select(Run.id)
        .where(Run.schedule_id == schedule_id, Run.status.in_(NON_TERMINAL))
        .order_by(Run.queued_at, Run.id)
        .limit(1)
    ).scalar_one_or_none()


def record_hole(
    db: Session,
    schedule: Schedule,
    at: datetime,
    reason: OccurrenceReason,
    blocking_run_id: UUID | None = None,
) -> None:
    db.add(
        ScheduleOccurrence(
            schedule_id=schedule.id,
            occurrence_at=at,
            reason=reason,
            blocking_run_id=blocking_run_id,
        )
    )


def prune_occurrences(db: Session, schedule_id: UUID) -> None:
    kept = (
        select(ScheduleOccurrence.id)
        .where(ScheduleOccurrence.schedule_id == schedule_id)
        .order_by(ScheduleOccurrence.occurrence_at.desc(), ScheduleOccurrence.id.desc())
        .limit(OCCURRENCE_PRUNE_DEPTH)
        .subquery()
    )
    db.execute(
        delete(ScheduleOccurrence).where(
            ScheduleOccurrence.schedule_id == schedule_id,
            ScheduleOccurrence.id.not_in(select(kept.c.id)),
        )
    )


def enqueue_latest(
    db: Session, schedule: Schedule, published: WorkflowVersion, now: datetime
) -> UUID:
    run = Run(
        org_id=schedule.org_id,
        starter_user_id=None,
        workflow_id=schedule.workflow_id,
        version_number=published.number,
        trigger=RunTrigger.SCHEDULE,
        schedule_id=schedule.id,
        status=RunStatus.QUEUED,
        variables=dict(schedule.variables),
        timeout_ms=DEFAULT_RUN_TIMEOUT_MS,
    )
    db.add(run)
    db.flush()
    schedule.last_fired_at = now
    return run.id
