from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from step_by_step_core.bus import DISPATCH_LIST, get_redis
from step_by_step_core.db import session_scope
from step_by_step_core.events import publish_batch

from step_by_step_api import clock
from step_by_step_api.batches.models import Batch, BatchRow, BatchRowStatus
from step_by_step_api.runs.models import (
    DEFAULT_RUN_TIMEOUT_MS,
    NON_TERMINAL,
    Run,
    RunStatus,
    RunTrigger,
)
from step_by_step_api.workflows.models import WorkflowVersion


@dataclass(frozen=True, slots=True)
class RowEvent:
    batch_id: UUID
    row_index: int
    status: str
    run_id: UUID | None
    at: datetime


def on_terminal_run(run_id: UUID) -> list[UUID]:
    with session_scope() as db:
        run = db.get(Run, run_id)
        if run is None or run.batch_row_id is None:
            return []
        if run.status.value in NON_TERMINAL:
            return []
        row = db.get(BatchRow, run.batch_row_id)
        if row is None:
            return []
        started, events = reflect_and_advance(db, row.batch_id)
        db.commit()
    emit(events)
    enqueue(started)
    return started


def advance_stalled_batches(
    db: Session, now: datetime
) -> tuple[list[UUID], list[RowEvent]]:
    batch_ids = list(
        db.execute(
            select(Batch.id)
            .join(BatchRow, BatchRow.batch_id == Batch.id)
            .where(BatchRow.status.in_((BatchRowStatus.QUEUED, BatchRowStatus.RUNNING)))
            .distinct()
            .order_by(Batch.id)
        ).scalars()
    )
    started: list[UUID] = []
    events: list[RowEvent] = []
    for batch_id in batch_ids:
        run_ids, row_events = reflect_and_advance(db, batch_id, now=now)
        started.extend(run_ids)
        events.extend(row_events)
    return started, events


def reflect_and_advance(
    db: Session, batch_id: UUID, now: datetime | None = None
) -> tuple[list[UUID], list[RowEvent]]:
    batch = db.execute(
        select(Batch).where(Batch.id == batch_id).with_for_update()
    ).scalar_one_or_none()
    if batch is None:
        return [], []
    at = now or clock.now()
    events: list[RowEvent] = []
    events.extend(reflect_running_rows(db, batch.id, at))
    started, started_event = start_next_queued(db, batch, at)
    if started_event is not None:
        events.append(started_event)
    if started is None:
        return [], events
    return [started], events


def reflect_running_rows(db: Session, batch_id: UUID, at: datetime) -> list[RowEvent]:
    events: list[RowEvent] = []
    running = db.execute(
        select(BatchRow)
        .where(BatchRow.batch_id == batch_id, BatchRow.status == BatchRowStatus.RUNNING)
        .order_by(BatchRow.index)
    ).scalars()
    for row in running:
        latest = latest_run(db, row.id)
        if latest is None or latest.status.value in NON_TERMINAL:
            continue
        new_status = status_from_run(latest, row.status)
        if new_status is row.status:
            continue
        row.status = new_status
        events.append(
            RowEvent(
                batch_id=batch_id,
                row_index=row.index,
                status=new_status.value,
                run_id=latest.id,
                at=at,
            )
        )
    return events


def start_next_queued(
    db: Session, batch: Batch, at: datetime
) -> tuple[UUID | None, RowEvent | None]:
    if batch.cancelled_at is not None:
        return None, None
    if open_run_id(db, batch.id) is not None:
        return None, None
    row = db.execute(
        select(BatchRow)
        .where(BatchRow.batch_id == batch.id, BatchRow.status == BatchRowStatus.QUEUED)
        .order_by(BatchRow.index)
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None, None
    published = latest_published(db, batch.workflow_id)
    if published is None:
        return None, None
    run = enqueue_row(db, batch, row, published)
    row.status = BatchRowStatus.RUNNING
    return run.id, RowEvent(
        batch_id=batch.id,
        row_index=row.index,
        status=BatchRowStatus.RUNNING.value,
        run_id=run.id,
        at=at,
    )


def enqueue_row(
    db: Session, batch: Batch, row: BatchRow, published: WorkflowVersion
) -> Run:
    run = Run(
        org_id=batch.org_id,
        starter_user_id=None,
        workflow_id=batch.workflow_id,
        version_number=published.number,
        trigger=RunTrigger.BATCH,
        batch_row_id=row.id,
        status=RunStatus.QUEUED,
        variables=dict(row.variables),
        timeout_ms=DEFAULT_RUN_TIMEOUT_MS,
    )
    db.add(run)
    db.flush()
    return run


def latest_published(db: Session, workflow_id: UUID) -> WorkflowVersion | None:
    return db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_run(db: Session, batch_row_id: UUID) -> Run | None:
    return db.execute(
        select(Run)
        .where(Run.batch_row_id == batch_row_id)
        .order_by(Run.queued_at.desc(), Run.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def open_run_id(db: Session, batch_id: UUID) -> UUID | None:
    return db.execute(
        select(Run.id)
        .join(BatchRow, BatchRow.id == Run.batch_row_id)
        .where(BatchRow.batch_id == batch_id, Run.status.in_(NON_TERMINAL))
        .order_by(Run.queued_at, Run.id)
        .limit(1)
    ).scalar_one_or_none()


def status_from_run(run: Run, current: BatchRowStatus) -> BatchRowStatus:
    if current is BatchRowStatus.SKIPPED:
        return current
    if run.status is RunStatus.SUCCEEDED:
        return BatchRowStatus.SUCCEEDED
    if run.status is RunStatus.FAILED:
        return BatchRowStatus.FAILED
    if run.status is RunStatus.CANCELLED:
        return BatchRowStatus.CANCELLED
    return current


def declared_variable_names(document: dict) -> set[str]:
    return {variable["name"] for variable in document.get("variables", [])}


def public_variable_names(document: dict) -> set[str]:
    return {
        variable["name"]
        for variable in document.get("variables", [])
        if not variable.get("secret", False)
    }


def stored_variables(asked: dict, names: set[str]) -> dict:
    return {name: value for name, value in asked.items() if name in names}


def has_value(variables: dict, name: str) -> bool:
    if name not in variables:
        return False
    value = variables[name]
    return value is not None and value != ""


def is_incomplete(variables: dict, names: set[str]) -> bool:
    return any(not has_value(variables, name) for name in names)


def enqueue(run_ids: list[UUID]) -> None:
    if not run_ids:
        return
    redis = get_redis()
    for run_id in run_ids:
        redis.lpush(DISPATCH_LIST, str(run_id))


def emit(events: list[RowEvent]) -> None:
    for event in events:
        publish_batch(
            event.batch_id,
            "batch.row",
            {
                "batch_id": event.batch_id,
                "row_index": event.row_index,
                "status": event.status,
                "run_id": event.run_id,
                "at": event.at,
            },
        )


def emit_row(
    batch_id: UUID,
    row_index: int,
    status: str,
    run_id: UUID | None,
    at: datetime | None = None,
) -> None:
    emit(
        [
            RowEvent(
                batch_id=batch_id,
                row_index=row_index,
                status=status,
                run_id=run_id,
                at=at or clock.now(),
            )
        ]
    )
