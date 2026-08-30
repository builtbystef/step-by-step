from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from step_by_step_api.runs.models import (
    FailureReason,
    Run,
    RunControlInterval,
    RunStatus,
    StepResult,
    StepResultStatus,
)
from step_by_step_api.workflows.models import WorkflowVersion

HEARTBEAT_STALE_AFTER = timedelta(seconds=90)

QUEUED_BACKSTOP_AFTER = timedelta(seconds=60)

LIVE = (RunStatus.RUNNING, RunStatus.WAITING_FOR_HUMAN)


def reap_and_backstop(db: Session, now: datetime) -> list[UUID]:
    reap_lost_workers(db, now)
    reap_takeover_deadlines(db, now)
    return queued_without_a_worker(db, now)


def reap_lost_workers(db: Session, now: datetime) -> None:
    stale = db.execute(
        select(Run)
        .where(
            Run.status.in_(LIVE),
            Run.heartbeat_at.is_not(None),
            Run.heartbeat_at < now - HEARTBEAT_STALE_AFTER,
        )
        .with_for_update()
        .order_by(Run.id)
    ).scalars()
    for run in stale:
        fail_worker_lost(db, run, now)


def fail_worker_lost(db: Session, run: Run, now: datetime) -> None:
    run.status = RunStatus.FAILED
    run.failure_reason = FailureReason.WORKER_LOST
    run.failure_detail = "the Worker stopped heartbeating"
    run.ended_at = now
    skip_unreached(db, run, now)


def reap_takeover_deadlines(db: Session, now: datetime) -> None:
    overdue = db.execute(
        select(Run)
        .where(
            Run.status == RunStatus.WAITING_FOR_HUMAN,
            Run.takeover_deadline_at.is_not(None),
            Run.takeover_deadline_at < now,
        )
        .with_for_update()
        .order_by(Run.id)
    ).scalars()
    for run in overdue:
        close_waiting_run(
            db,
            run,
            now,
            status=RunStatus.FAILED,
            failure_reason=FailureReason.TAKEOVER_TIMEOUT,
            fail_paused=True,
        )


def end_open_intervals(db: Session, run_id: UUID, now: datetime) -> None:
    open_rows = db.execute(
        select(RunControlInterval).where(
            RunControlInterval.run_id == run_id,
            RunControlInterval.ended_at.is_(None),
        )
    ).scalars()
    for interval in open_rows:
        interval.ended_at = now


def close_waiting_run(
    db: Session,
    run: Run,
    now: datetime,
    *,
    status: RunStatus,
    failure_reason: FailureReason | None = None,
    fail_paused: bool = False,
) -> None:
    run.status = status
    run.failure_reason = failure_reason
    run.ended_at = now
    run.takeover_holder_session_id = None
    end_open_intervals(db, run.id, now)
    if fail_paused:
        fail_paused_and_skip_rest(db, run, now)
    else:
        skip_unreached(db, run, now)


def fail_paused_and_skip_rest(db: Session, run: Run, now: datetime) -> None:
    written = set(
        db.execute(select(StepResult.position).where(StepResult.run_id == run.id))
        .scalars()
        .all()
    )
    pending = True
    for position, step in enumerate(steps_of(db, run)):
        if position in written:
            continue
        db.add(
            StepResult(
                run_id=run.id,
                step_id=UUID(str(step["id"])),
                position=position,
                status=StepResultStatus.FAILED if pending else StepResultStatus.SKIPPED,
                ended_at=now,
            )
        )
        pending = False


def skip_unreached(db: Session, run: Run, now: datetime) -> None:
    written = set(
        db.execute(select(StepResult.position).where(StepResult.run_id == run.id))
        .scalars()
        .all()
    )
    for position, step in enumerate(steps_of(db, run)):
        if position in written:
            continue
        db.add(
            StepResult(
                run_id=run.id,
                step_id=UUID(str(step["id"])),
                position=position,
                status=StepResultStatus.SKIPPED,
                ended_at=now,
            )
        )


def steps_of(db: Session, run: Run) -> list[dict[str, object]]:
    document = run.draft_snapshot
    if document is None and run.version_number is not None:
        version = db.get(WorkflowVersion, (run.workflow_id, run.version_number))
        document = None if version is None else version.document
    if not document:
        return []
    return list(document.get("steps", []))


def queued_without_a_worker(db: Session, now: datetime) -> list[UUID]:
    return list(
        db.execute(
            select(Run.id)
            .where(
                Run.status == RunStatus.QUEUED,
                Run.worker_id.is_(None),
                Run.queued_at < now - QUEUED_BACKSTOP_AFTER,
            )
            .order_by(Run.queued_at, Run.id)
        ).scalars()
    )
