"""Fire every enabled Schedule whose current occurrence has passed."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from step_by_step_api.runs.models import (
    DEFAULT_RUN_TIMEOUT_MS,
    NON_TERMINAL,
    Run,
    RunStatus,
    RunTrigger,
)
from step_by_step_api.schedules.cron import next_occurrence
from step_by_step_api.schedules.models import SKIP_OVERLAP, Schedule
from step_by_step_api.workflows.models import WorkflowVersion


def fire_due_schedules(db: Session, now: datetime) -> list[UUID]:
    """Create at most one Run per due Schedule, then jump next_due_at into the future.

    An occurrence is due when `next_due_at` is in the past and no later occurrence
    of the same expression has also passed — missed occurrences are skipped, never
    caught up. A still-non-terminal Run of this Schedule records `overlap` instead
    of a second Run.
    """
    due = db.execute(
        select(Schedule)
        .where(Schedule.enabled.is_(True), Schedule.next_due_at <= now)
        .with_for_update()
        .order_by(Schedule.next_due_at, Schedule.id)
    ).scalars()
    run_ids: list[UUID] = []
    for schedule in due:
        following = next_occurrence(
            schedule.cron, schedule.timezone, schedule.next_due_at
        )
        if following > now:
            if has_open_run(db, schedule.id):
                schedule.last_skip_reason = SKIP_OVERLAP
            else:
                run_id = enqueue_latest(db, schedule, now)
                if run_id is not None:
                    run_ids.append(run_id)
        schedule.next_due_at = next_occurrence(schedule.cron, schedule.timezone, now)
    return run_ids


def has_open_run(db: Session, schedule_id: UUID) -> bool:
    """True when a Run of this Schedule is still queued, running, or waiting."""
    found = db.execute(
        select(Run.id)
        .where(Run.schedule_id == schedule_id, Run.status.in_(NON_TERMINAL))
        .limit(1)
    ).scalar_one_or_none()
    return found is not None


def enqueue_latest(db: Session, schedule: Schedule, now: datetime) -> UUID | None:
    """Queue a Run of the Workflow's latest published Version, or skip if none."""
    published = db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == schedule.workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()
    if published is None:
        return None
    run = Run(
        org_id=schedule.org_id,
        starter_user_id=None,
        workflow_id=schedule.workflow_id,
        version_number=published.number,
        trigger=RunTrigger.SCHEDULE,
        schedule_id=schedule.id,
        status=RunStatus.QUEUED,
        variables={},
        timeout_ms=DEFAULT_RUN_TIMEOUT_MS,
    )
    db.add(run)
    db.flush()
    schedule.last_fired_at = now
    schedule.last_skip_reason = None
    return run.id
