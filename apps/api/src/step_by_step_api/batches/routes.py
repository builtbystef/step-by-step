from __future__ import annotations

import csv
import io
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, literal, select, tuple_
from sqlalchemy.orm import Session
from step_by_step_core.bus import control_channel, get_redis
from step_by_step_core.events import batch_events_channel

from step_by_step_api import clock
from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.batches.advance import (
    RowEvent,
    declared_variable_names,
    emit,
    emit_row,
    enqueue,
    has_value,
    is_incomplete,
    latest_published,
    latest_run,
    public_variable_names,
    start_next_queued,
    stored_variables,
)
from step_by_step_api.batches.models import (
    MAX_BATCH_ROWS,
    Batch,
    BatchRow,
    BatchRowStatus,
)
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.runs.models import (
    NON_TERMINAL,
    Run,
    RunStatus,
    StepResult,
)
from step_by_step_api.runs.reap import close_waiting_run
from step_by_step_api.workflows.models import Workflow

router = APIRouter(tags=["batches"])
PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
EDITABLE_ROW_STATUSES = (
    BatchRowStatus.QUEUED,
    BatchRowStatus.SKIPPED,
    BatchRowStatus.FAILED,
)


class BatchRowInput(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)


class CreateBatch(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    rows: list[BatchRowInput] = Field(default_factory=list)
    run_incomplete_rows: bool = False


class BatchCreated(BaseModel):
    batch_id: UUID


class RerunCreated(BaseModel):
    run_id: UUID


class BatchRecord(BaseModel):
    id: UUID
    name: str
    workflow_id: UUID
    created_at: datetime
    cancelled_at: datetime | None


class AttemptRecord(BaseModel):
    id: UUID
    status: RunStatus
    failure_reason: str | None
    queued_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class BatchRowRecord(BaseModel):
    index: int
    variables: dict[str, Any]
    status: BatchRowStatus
    latest_run_id: UUID | None
    runs: list[AttemptRecord]


class BatchStats(BaseModel):
    queued: int
    running: int
    succeeded: int
    failed: int
    skipped: int
    cancelled: int


class BatchSummary(BaseModel):
    id: UUID
    name: str
    workflow_id: UUID
    created_at: datetime
    cancelled_at: datetime | None
    row_count: int
    stats: BatchStats


class BatchPage(BaseModel):
    items: list[BatchSummary]
    next_cursor: str | None = None


class FillRows(BaseModel):
    name: str
    value: Any


class FillResult(BaseModel):
    updated_count: int


class BatchDetail(BaseModel):
    batch: BatchRecord
    rows: list[BatchRowRecord]
    stats: BatchStats
    eta_seconds: int | None = None


class OutputTable(BaseModel):
    columns: list[str]
    rows: list[list[Any]]


class BatchRowRef(BaseModel):
    batch_id: UUID
    index: int
    status: BatchRowStatus
    variables: dict[str, Any]


def owned_workflow(db: SessionDep, org_id: UUID, workflow_id: UUID) -> Workflow:
    found = db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.org_id == org_id)
    ).scalar_one_or_none()
    if found is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    return found


def owned_batch(db: SessionDep, org_id: UUID, batch_id: UUID) -> Batch:
    found = db.execute(
        select(Batch).where(Batch.id == batch_id, Batch.org_id == org_id)
    ).scalar_one_or_none()
    if found is None:
        raise ApiError(404, "batch_not_found", "no such Batch")
    return found


def owned_row(db: SessionDep, batch: Batch, index: int) -> BatchRow:
    found = db.execute(
        select(BatchRow).where(BatchRow.batch_id == batch.id, BatchRow.index == index)
    ).scalar_one_or_none()
    if found is None:
        raise ApiError(404, "batch_row_not_found", "no such Batch row")
    return found


@router.post(
    "/api/workflows/{workflow_id}/batches",
    operation_id="createBatch",
    status_code=201,
    responses=errors(400, 401, 403, 404, 409, 413),
)
def create_batch(
    workflow_id: UUID,
    asked: CreateBatch,
    member: ActiveMembership,
    db: SessionDep,
) -> BatchCreated:
    owned_workflow(db, member.org_id, workflow_id)
    published = latest_published(db, workflow_id)
    if published is None:
        raise ApiError(
            409,
            "no_published_version",
            "Publish a Version before this Workflow can run.",
        )
    if len(asked.rows) > MAX_BATCH_ROWS:
        raise ApiError(
            413,
            "too_many_rows",
            f"a Batch may hold at most {MAX_BATCH_ROWS} rows",
            max=MAX_BATCH_ROWS,
        )
    declared = declared_variable_names(published.document)
    unknown = sorted(
        {name for row in asked.rows for name in row.variables if name not in declared}
    )
    if unknown:
        raise ApiError(
            400,
            "unknown_variable",
            "those Variables are not declared on the latest published Version",
            names=unknown,
        )
    names = public_variable_names(published.document)
    batch = Batch(org_id=member.org_id, workflow_id=workflow_id, name=asked.name)
    db.add(batch)
    db.flush()
    for index, row in enumerate(asked.rows):
        stored = stored_variables(row.variables, names)
        incomplete = is_incomplete(stored, names)
        status = (
            BatchRowStatus.QUEUED
            if asked.run_incomplete_rows or not incomplete
            else BatchRowStatus.SKIPPED
        )
        db.add(
            BatchRow(
                batch_id=batch.id,
                index=index,
                variables=stored,
                status=status,
            )
        )
    db.flush()
    started, started_event = start_next_queued(db, batch, clock.now())
    db.commit()
    if started is not None:
        enqueue([started])
    if started_event is not None:
        emit([started_event])
    return BatchCreated(batch_id=batch.id)


@router.get(
    "/api/batches",
    operation_id="listBatches",
    responses=errors(400, 401, 403, 404),
)
def list_batches(
    member: ActiveMembership,
    db: SessionDep,
    workflow_id: UUID,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = PAGE_SIZE,
    cursor: str | None = None,
) -> BatchPage:
    owned_workflow(db, member.org_id, workflow_id)
    conditions = [Batch.org_id == member.org_id, Batch.workflow_id == workflow_id]
    if cursor is not None:
        created_at, batch_id = read_batch_cursor(cursor)
        conditions.append(
            tuple_(Batch.created_at, Batch.id)
            < tuple_(literal(created_at), literal(batch_id))
        )
    rows = list(
        db.execute(
            select(Batch)
            .where(*conditions)
            .order_by(Batch.created_at.desc(), Batch.id.desc())
            .limit(limit + 1)
        ).scalars()
    )
    return BatchPage(
        items=summaries_of(db, rows[:limit]),
        next_cursor=batch_cursor_for(rows[limit - 1]) if len(rows) > limit else None,
    )


@router.get(
    "/api/batches/{batch_id}",
    operation_id="getBatch",
    responses=errors(400, 401, 403, 404),
)
def get_batch(batch_id: UUID, member: ActiveMembership, db: SessionDep) -> BatchDetail:
    batch = owned_batch(db, member.org_id, batch_id)
    rows = list(
        db.execute(
            select(BatchRow)
            .where(BatchRow.batch_id == batch.id)
            .order_by(BatchRow.index)
        ).scalars()
    )
    attempts = attempts_by_row(db, [row.id for row in rows])
    return BatchDetail(
        batch=BatchRecord(
            id=batch.id,
            name=batch.name,
            workflow_id=batch.workflow_id,
            created_at=batch.created_at,
            cancelled_at=batch.cancelled_at,
        ),
        rows=[row_record(row, attempts.get(row.id, [])) for row in rows],
        stats=stats_of(rows),
        eta_seconds=eta_of(rows, attempts),
    )


@router.get(
    "/api/batches/{batch_id}/output",
    operation_id="getBatchOutput",
    response_model=None,
    responses=errors(400, 401, 403, 404),
)
def get_batch_output(
    batch_id: UUID,
    member: ActiveMembership,
    db: SessionDep,
    format: Literal["json", "csv"] = Query(default="json"),
) -> OutputTable | Response:
    batch = owned_batch(db, member.org_id, batch_id)
    table = assemble_output(db, batch)
    if format == "csv":
        return Response(
            content=as_csv(table),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="batch.csv"'},
        )
    return table


@router.get(
    "/api/batches/{batch_id}/events",
    operation_id="streamBatchEvents",
    response_class=StreamingResponse,
    responses={
        **errors(400, 401, 403, 404),
        200: {
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
            "description": "Live Batch events. Reconnection replays nothing.",
        },
    },
)
def stream_batch_events(
    batch_id: UUID, member: ActiveMembership, db: SessionDep
) -> StreamingResponse:
    owned_batch(db, member.org_id, batch_id)
    from step_by_step_api.runs.routes import fan_out

    pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(batch_events_channel(batch_id))
    return StreamingResponse(
        fan_out(pubsub),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/api/batches/{batch_id}/cancel",
    operation_id="cancelBatch",
    status_code=202,
    responses=errors(400, 401, 403, 404),
)
def cancel_batch(batch_id: UUID, member: ActiveMembership, db: SessionDep) -> Response:
    batch = owned_batch(db, member.org_id, batch_id)
    now = clock.now()
    if batch.cancelled_at is None:
        batch.cancelled_at = now
    events: list[RowEvent] = []
    rows = list(
        db.execute(
            select(BatchRow)
            .where(BatchRow.batch_id == batch.id)
            .order_by(BatchRow.index)
        ).scalars()
    )
    for row in rows:
        if row.status is BatchRowStatus.QUEUED:
            row.status = BatchRowStatus.CANCELLED
            events.append(
                RowEvent(
                    batch_id=batch.id,
                    row_index=row.index,
                    status=BatchRowStatus.CANCELLED.value,
                    run_id=None,
                    at=now,
                )
            )
        elif row.status is BatchRowStatus.RUNNING:
            current = latest_run(db, row.id)
            if current is not None:
                cancel_current(db, current, now)
            if current is None or current.status.value not in NON_TERMINAL:
                row.status = BatchRowStatus.CANCELLED
                events.append(
                    RowEvent(
                        batch_id=batch.id,
                        row_index=row.index,
                        status=BatchRowStatus.CANCELLED.value,
                        run_id=None if current is None else current.id,
                        at=now,
                    )
                )
    db.commit()
    emit(events)
    return Response(status_code=202)


@router.patch(
    "/api/batches/{batch_id}/rows/{index}",
    operation_id="updateBatchRow",
    responses=errors(400, 401, 403, 404, 409),
)
def update_batch_row(
    batch_id: UUID,
    index: int,
    asked: BatchRowInput,
    member: ActiveMembership,
    db: SessionDep,
) -> BatchRowRecord:
    batch = owned_batch(db, member.org_id, batch_id)
    row = owned_row(db, batch, index)
    if row.status not in EDITABLE_ROW_STATUSES:
        raise ApiError(409, "row_not_editable", "that row's values cannot be changed")
    published = latest_published(db, batch.workflow_id)
    names = public_variable_names({} if published is None else published.document)
    row.variables = stored_variables(asked.variables, names)
    attempts = attempts_by_row(db, [row.id]).get(row.id, [])
    record = row_record(row, attempts)
    db.commit()
    return record


@router.post(
    "/api/batches/{batch_id}/rows/fill",
    operation_id="fillBatchRows",
    responses=errors(400, 401, 403, 404),
)
def fill_batch_rows(
    batch_id: UUID,
    asked: FillRows,
    member: ActiveMembership,
    db: SessionDep,
) -> FillResult:
    batch = owned_batch(db, member.org_id, batch_id)
    rows = list(
        db.execute(
            select(BatchRow)
            .where(
                BatchRow.batch_id == batch.id,
                BatchRow.status == BatchRowStatus.QUEUED,
            )
            .order_by(BatchRow.index)
        ).scalars()
    )
    updated = 0
    for row in rows:
        if has_value(row.variables, asked.name):
            continue
        row.variables = {**row.variables, asked.name: asked.value}
        updated += 1
    db.commit()
    return FillResult(updated_count=updated)


@router.post(
    "/api/batches/{batch_id}/rows/{index}/skip",
    operation_id="skipBatchRow",
    status_code=202,
    responses=errors(400, 401, 403, 404, 409),
)
def skip_batch_row(
    batch_id: UUID, index: int, member: ActiveMembership, db: SessionDep
) -> Response:
    batch = owned_batch(db, member.org_id, batch_id)
    row = owned_row(db, batch, index)
    current = latest_run(db, row.id)
    if current is None or current.status is not RunStatus.WAITING_FOR_HUMAN:
        raise ApiError(409, "not_waiting", "that row is not waiting for a person")
    now = clock.now()
    close_waiting_run(db, current, now, status=RunStatus.CANCELLED)
    row.status = BatchRowStatus.SKIPPED
    started, started_event = start_next_queued(db, batch, now)
    db.commit()
    if started is not None:
        enqueue([started])
    emit_row(batch.id, row.index, BatchRowStatus.SKIPPED.value, current.id, now)
    if started_event is not None:
        emit([started_event])
    return Response(status_code=202)


@router.post(
    "/api/batches/{batch_id}/rows/{index}/rerun",
    operation_id="rerunBatchRow",
    status_code=201,
    responses=errors(400, 401, 403, 404, 409),
)
def rerun_batch_row(
    batch_id: UUID, index: int, member: ActiveMembership, db: SessionDep
) -> RerunCreated:
    batch = owned_batch(db, member.org_id, batch_id)
    row = owned_row(db, batch, index)
    if row.status not in (BatchRowStatus.FAILED, BatchRowStatus.SKIPPED):
        raise ApiError(
            409, "row_not_rerunnable", "only a failed or skipped row can be re-run"
        )
    locked = db.execute(
        select(Batch).where(Batch.id == batch.id).with_for_update()
    ).scalar_one()
    from step_by_step_api.batches.advance import enqueue_row, open_run_id

    if open_run_id(db, locked.id) is not None:
        raise ApiError(409, "batch_busy", "another row of this Batch is still running")
    published = latest_published(db, locked.workflow_id)
    if published is None:
        raise ApiError(
            409,
            "no_published_version",
            "Publish a Version before this Workflow can run.",
        )
    now = clock.now()
    run = enqueue_row(db, locked, row, published)
    row.status = BatchRowStatus.RUNNING
    db.commit()
    enqueue([run.id])
    emit_row(locked.id, row.index, BatchRowStatus.RUNNING.value, run.id, now)
    return RerunCreated(run_id=run.id)


def cancel_current(db: Session, run: Run, now: datetime) -> None:
    if run.status.value not in NON_TERMINAL:
        return
    if run.status is RunStatus.QUEUED:
        run.status = RunStatus.CANCELLED
        run.ended_at = now
        return
    if run.status is RunStatus.WAITING_FOR_HUMAN:
        close_waiting_run(db, run, now, status=RunStatus.CANCELLED)
        return
    if run.cancel_requested_at is None:
        run.cancel_requested_at = now
    get_redis().publish(control_channel(run.id), json.dumps({"cancel_requested": True}))


def attempts_by_row(db: Session, row_ids: list[UUID]) -> dict[UUID, list[Run]]:
    if not row_ids:
        return {}
    found = db.execute(
        select(Run).where(Run.batch_row_id.in_(row_ids)).order_by(Run.queued_at, Run.id)
    ).scalars()
    grouped: dict[UUID, list[Run]] = {row_id: [] for row_id in row_ids}
    for run in found:
        if run.batch_row_id is not None:
            grouped.setdefault(run.batch_row_id, []).append(run)
    return grouped


def row_record(row: BatchRow, attempts: list[Run]) -> BatchRowRecord:
    latest = attempts[-1] if attempts else None
    return BatchRowRecord(
        index=row.index,
        variables=row.variables,
        status=row.status,
        latest_run_id=None if latest is None else latest.id,
        runs=[
            AttemptRecord(
                id=run.id,
                status=run.status,
                failure_reason=None
                if run.failure_reason is None
                else run.failure_reason.value,
                queued_at=run.queued_at,
                started_at=run.started_at,
                ended_at=run.ended_at,
            )
            for run in attempts
        ],
    )


def summaries_of(db: Session, batches: list[Batch]) -> list[BatchSummary]:
    counts = counts_by_batch(db, [batch.id for batch in batches])
    return [batch_summary(batch, counts.get(batch.id, {})) for batch in batches]


def counts_by_batch(
    db: Session, batch_ids: list[UUID]
) -> dict[UUID, dict[BatchRowStatus, int]]:
    if not batch_ids:
        return {}
    grouped: dict[UUID, dict[BatchRowStatus, int]] = {
        batch_id: {status: 0 for status in BatchRowStatus} for batch_id in batch_ids
    }
    rows = db.execute(
        select(BatchRow.batch_id, BatchRow.status, func.count())
        .where(BatchRow.batch_id.in_(batch_ids))
        .group_by(BatchRow.batch_id, BatchRow.status)
    ).all()
    for batch_id, status, n in rows:
        grouped[batch_id][status] = n
    return grouped


def batch_summary(batch: Batch, counts: dict[BatchRowStatus, int]) -> BatchSummary:
    tallies = {status: counts.get(status, 0) for status in BatchRowStatus}
    return BatchSummary(
        id=batch.id,
        name=batch.name,
        workflow_id=batch.workflow_id,
        created_at=batch.created_at,
        cancelled_at=batch.cancelled_at,
        row_count=sum(tallies.values()),
        stats=BatchStats(
            queued=tallies[BatchRowStatus.QUEUED],
            running=tallies[BatchRowStatus.RUNNING],
            succeeded=tallies[BatchRowStatus.SUCCEEDED],
            failed=tallies[BatchRowStatus.FAILED],
            skipped=tallies[BatchRowStatus.SKIPPED],
            cancelled=tallies[BatchRowStatus.CANCELLED],
        ),
    )


def batch_cursor_for(batch: Batch) -> str:
    return urlsafe_b64encode(
        json.dumps({"at": batch.created_at.isoformat(), "id": str(batch.id)}).encode()
    ).decode()


def read_batch_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        payload = json.loads(urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(payload["at"]), UUID(payload["id"])
    except Exception:
        raise ApiError(
            400, "bad_cursor", "that cursor did not come from this list"
        ) from None


def stats_of(rows: list[BatchRow]) -> BatchStats:
    counts = {status: 0 for status in BatchRowStatus}
    for row in rows:
        counts[row.status] += 1
    return BatchStats(
        queued=counts[BatchRowStatus.QUEUED],
        running=counts[BatchRowStatus.RUNNING],
        succeeded=counts[BatchRowStatus.SUCCEEDED],
        failed=counts[BatchRowStatus.FAILED],
        skipped=counts[BatchRowStatus.SKIPPED],
        cancelled=counts[BatchRowStatus.CANCELLED],
    )


def eta_of(rows: list[BatchRow], attempts: dict[UUID, list[Run]]) -> int | None:
    durations: list[float] = []
    for row in rows:
        if row.status not in (BatchRowStatus.SUCCEEDED, BatchRowStatus.FAILED):
            continue
        latest = attempts.get(row.id, [])
        if not latest:
            continue
        run = latest[-1]
        if run.ended_at is None:
            continue
        start = run.started_at or run.queued_at
        durations.append((run.ended_at - start).total_seconds())
    if len(durations) < 3:
        return None
    remaining = sum(
        1
        for row in rows
        if row.status in (BatchRowStatus.QUEUED, BatchRowStatus.RUNNING)
    )
    return int(median(durations) * remaining)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def assemble_output(db: Session, batch: Batch) -> OutputTable:
    published = latest_published(db, batch.workflow_id)
    document = {} if published is None else published.document
    rows = list(
        db.execute(
            select(BatchRow)
            .where(BatchRow.batch_id == batch.id)
            .order_by(BatchRow.index)
        ).scalars()
    )
    variable_names = output_variable_names(document, rows)
    extract_names = output_extract_names(document)
    columns = variable_names + [
        name for name in extract_names if name not in variable_names
    ]
    extracts = extracts_by_row(db, document, [row.id for row in rows])
    table_rows: list[list[Any]] = []
    for row in rows:
        values = dict(row.variables)
        values.update(extracts.get(row.id, {}))
        table_rows.append([values.get(column) for column in columns])
    return OutputTable(columns=columns, rows=table_rows)


def output_variable_names(document: dict[str, Any], rows: list[BatchRow]) -> list[str]:
    names = [
        variable["name"]
        for variable in document.get("variables", [])
        if not variable.get("secret", False)
    ]
    seen = set(names)
    for row in rows:
        for name in row.variables:
            if name not in seen:
                names.append(name)
                seen.add(name)
    return names


def output_extract_names(document: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for step in document.get("steps", []):
        if step.get("type") != "extract":
            continue
        payload = step.get("payload") or {}
        name = payload.get("outputName")
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def extracts_by_row(
    db: Session, document: dict[str, Any], row_ids: list[UUID]
) -> dict[UUID, dict[str, Any]]:
    if not row_ids:
        return {}
    step_names: dict[str, str] = {}
    for step in document.get("steps", []):
        if step.get("type") != "extract":
            continue
        payload = step.get("payload") or {}
        name = payload.get("outputName")
        step_id = step.get("id")
        if isinstance(name, str) and isinstance(step_id, str):
            step_names[step_id] = name
    if not step_names:
        return {}
    attempts = attempts_by_row(db, row_ids)
    latest_ids = [runs[-1].id for runs in attempts.values() if runs]
    if not latest_ids:
        return {}
    results = db.execute(
        select(StepResult, Run.batch_row_id)
        .join(Run, Run.id == StepResult.run_id)
        .where(
            StepResult.run_id.in_(latest_ids), StepResult.extracted_value.is_not(None)
        )
    ).all()
    by_row: dict[UUID, dict[str, Any]] = {}
    for result, batch_row_id in results:
        if batch_row_id is None:
            continue
        name = step_names.get(str(result.step_id))
        if name is None:
            continue
        by_row.setdefault(batch_row_id, {})[name] = result.extracted_value
    return by_row


def as_csv(table: OutputTable) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(table.columns)
    for row in table.rows:
        writer.writerow(["" if cell is None else cell for cell in row])
    return buffer.getvalue()


def batch_row_ref(db: Session, run: Run) -> BatchRowRef | None:
    if run.batch_row_id is None:
        return None
    row = db.get(BatchRow, run.batch_row_id)
    if row is None:
        return None
    return BatchRowRef(
        batch_id=row.batch_id,
        index=row.index,
        status=row.status,
        variables=row.variables,
    )
