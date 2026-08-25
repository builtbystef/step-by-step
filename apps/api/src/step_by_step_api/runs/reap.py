"""Reap stale heartbeats and re-enqueue queued Runs the dispatch list dropped."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from step_by_step_api.runs.models import (
    FailureReason,
    Run,
    RunStatus,
    StepResult,
    StepResultStatus,
)
from step_by_step_api.workflows.models import WorkflowVersion

HEARTBEAT_STALE_AFTER = timedelta(seconds=90)
"""A Worker beats every few seconds; two missed ticks is gone, not slow."""

QUEUED_BACKSTOP_AFTER = timedelta(seconds=60)
"""Longer than one loop interval, so a just-enqueued id is not pushed again."""

LIVE = (RunStatus.RUNNING, RunStatus.WAITING_FOR_HUMAN)


def reap_and_backstop(db: Session, now: datetime) -> list[UUID]:
    """Fail lost Workers' Runs, and return queued ids the list should hold again."""
    reap_lost_workers(db, now)
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


def skip_unreached(db: Session, run: Run, now: datetime) -> None:
    """Write a skipped Step Result for every Step the Run never reached."""
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
