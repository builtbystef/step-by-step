"""The user-facing Run start, list, detail, events, logs, and cancellation."""

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func, literal, select, tuple_
from step_by_step_core.bus import DISPATCH_LIST, control_channel, get_redis
from step_by_step_core.events import events_channel

from step_by_step_api import clock
from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.accounts.sessions import SESSION_COOKIE, token_digest
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.runs.models import (
    DEFAULT_RUN_TIMEOUT_MS,
    NON_TERMINAL,
    FailureReason,
    LogLevel,
    Run,
    RunControlInterval,
    RunControlKind,
    RunLogLine,
    RunStatus,
    RunTrigger,
    StepResult,
    StepResultStatus,
)
from step_by_step_api.runs.reap import close_waiting_run
from step_by_step_api.runs.tickets import mint_ticket
from step_by_step_api.workflows.models import Workflow, WorkflowDraft, WorkflowVersion

router = APIRouter(tags=["runs"])
PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class StartRun(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    test: bool = False


class RunCreated(BaseModel):
    run_id: UUID


class RunRecord(BaseModel):
    id: UUID
    workflow_id: UUID
    version_number: int | None
    draft_snapshot: dict[str, Any] | None
    is_test: bool
    trigger: RunTrigger
    status: RunStatus
    failure_reason: FailureReason | None
    failure_detail: str | None
    variables: dict[str, Any]
    timeout_ms: int
    worker_id: str | None
    worker_vnc_endpoint: str | None
    heartbeat_at: datetime | None
    cancel_requested_at: datetime | None
    pause_requested_at: datetime | None
    takeover_deadline_at: datetime | None
    auto_handback_disabled: bool
    queued_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    automation_ms: int


class RunSummary(BaseModel):
    id: UUID
    workflow_id: UUID
    version_number: int | None
    trigger: RunTrigger
    status: RunStatus
    failure_reason: FailureReason | None
    queued_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class RunPage(BaseModel):
    items: list[RunSummary]
    next_cursor: str | None = None


class WaitingAttention(BaseModel):
    run_id: UUID
    workflow_id: UUID
    workflow_name: str
    deadline_at: datetime


class Attention(BaseModel):
    waiting: list[WaitingAttention]
    waiting_count: int
    running_count: int
    queued_count: int


class StepResultRecord(BaseModel):
    id: UUID
    step_id: UUID
    position: int
    status: StepResultStatus
    started_at: datetime | None
    ended_at: datetime | None
    matched_candidate_rank: int | None
    candidate_count: int | None
    completed_by_human: bool
    error_code: str | None
    error_message: str | None
    diagnostics: dict[str, Any] | None
    extracted_value: Any | None


class ControlIntervalRecord(BaseModel):
    id: UUID
    kind: RunControlKind
    started_at: datetime
    ended_at: datetime | None


class RunDetail(BaseModel):
    run: RunRecord
    step_results: list[StepResultRecord]
    control_intervals: list[ControlIntervalRecord]
    artifacts: list[dict[str, Any]]
    batch_row: dict[str, Any] | None


class LogLine(BaseModel):
    seq: int
    step_id: UUID | None
    level: LogLevel
    text: str
    at: datetime


class TakeoverTicket(BaseModel):
    ticket: str
    ws_url: str
    expires_at: datetime
    deadline_at: datetime | None


def workflow_to_run(
    db: SessionDep,
    member: ActiveMembership,
    workflow_id: UUID,
    asked: StartRun,
) -> Run:
    """Build the queued row from the Draft or latest immutable Version."""
    row = db.execute(
        select(Workflow, WorkflowDraft)
        .join(WorkflowDraft, WorkflowDraft.workflow_id == Workflow.id)
        .where(Workflow.id == workflow_id, Workflow.org_id == member.org_id)
    ).one_or_none()
    if row is None:
        raise ApiError(404, "workflow_not_found", "no such Workflow")
    _, draft = row
    published = db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
    ).scalar_one_or_none()
    if asked.test:
        document = draft.document
        version_number = None
    else:
        if published is None:
            raise ApiError(
                409,
                "no_published_version",
                "Publish a Version before this Workflow can run.",
            )
        document = published.document
        version_number = published.number
    public_names = {
        variable["name"]
        for variable in document.get("variables", [])
        if not variable.get("secret", False)
    }
    return Run(
        org_id=member.org_id,
        starter_user_id=member.user_id,
        workflow_id=workflow_id,
        version_number=version_number,
        draft_snapshot=draft.document if asked.test else None,
        is_test=asked.test,
        trigger=RunTrigger.TEST if asked.test else RunTrigger.MANUAL,
        status=RunStatus.QUEUED,
        variables={
            name: value
            for name, value in asked.variables.items()
            if name in public_names
        },
        timeout_ms=DEFAULT_RUN_TIMEOUT_MS,
    )


@router.post(
    "/api/workflows/{workflow_id}/runs",
    operation_id="startRun",
    status_code=201,
    responses=errors(400, 401, 403, 404, 409),
)
def start_run(
    workflow_id: UUID,
    asked: StartRun,
    member: ActiveMembership,
    db: SessionDep,
) -> RunCreated:
    """Persist one queued Run, then place its id on the dumb dispatch pipe."""
    run = workflow_to_run(db, member, workflow_id, asked)
    db.add(run)
    db.commit()
    get_redis().lpush(DISPATCH_LIST, str(run.id))
    return RunCreated(run_id=run.id)


@router.get(
    "/api/runs",
    operation_id="listRuns",
    response_model_exclude_none=True,
    responses=errors(400, 401, 403),
)
def list_runs(
    member: ActiveMembership,
    db: SessionDep,
    workflow_id: UUID | None = None,
    status: RunStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = PAGE_SIZE,
    cursor: str | None = None,
) -> RunPage:
    """Runs in newest-first order, optionally narrowed by Workflow and status."""
    conditions = [Run.org_id == member.org_id]
    if workflow_id is not None:
        conditions.append(Run.workflow_id == workflow_id)
    if status is not None:
        conditions.append(Run.status == status)
    if cursor is not None:
        queued_at, run_id = read_cursor(cursor)
        conditions.append(
            tuple_(Run.queued_at, Run.id) < tuple_(literal(queued_at), literal(run_id))
        )
    rows = list(
        db.execute(
            select(Run)
            .where(*conditions)
            .order_by(Run.queued_at.desc(), Run.id.desc())
            .limit(limit + 1)
        ).scalars()
    )
    return RunPage(
        items=[run_summary(run) for run in rows[:limit]],
        next_cursor=cursor_for(rows[limit - 1]) if len(rows) > limit else None,
    )


def attention_statement(org_id: UUID):
    """One index-bounded scan for both the waiting head and all three counts."""
    waiting = Run.status == RunStatus.WAITING_FOR_HUMAN
    return (
        select(
            Run.id.label("run_id"),
            Run.workflow_id,
            Workflow.name.label("workflow_name"),
            Run.status,
            Run.takeover_deadline_at.label("deadline_at"),
            func.count().filter(waiting).over().label("waiting_count"),
            func.count()
            .filter(Run.status == RunStatus.RUNNING)
            .over()
            .label("running_count"),
            func.count()
            .filter(Run.status == RunStatus.QUEUED)
            .over()
            .label("queued_count"),
        )
        .join(Workflow, Workflow.id == Run.workflow_id)
        .where(Run.org_id == org_id, Run.status.in_(NON_TERMINAL))
        .order_by(
            case((waiting, 0), else_=1),
            Run.takeover_deadline_at.asc().nulls_last(),
            Run.id,
        )
        .limit(5)
    )


@router.get(
    "/api/attention",
    operation_id="getAttention",
    responses=errors(400, 401, 403),
)
def get_attention(member: ActiveMembership, db: SessionDep) -> Attention:
    """The active Organization's non-terminal Run summary for the shell."""
    rows = db.execute(attention_statement(member.org_id)).all()
    if not rows:
        return Attention(waiting=[], waiting_count=0, running_count=0, queued_count=0)
    first = rows[0]
    return Attention(
        waiting=[
            WaitingAttention(
                run_id=row.run_id,
                workflow_id=row.workflow_id,
                workflow_name=row.workflow_name,
                deadline_at=row.deadline_at,
            )
            for row in rows
            if row.status is RunStatus.WAITING_FOR_HUMAN and row.deadline_at is not None
        ],
        waiting_count=first.waiting_count,
        running_count=first.running_count,
        queued_count=first.queued_count,
    )


def cursor_for(run: Run) -> str:
    return urlsafe_b64encode(
        json.dumps({"at": run.queued_at.isoformat(), "id": str(run.id)}).encode()
    ).decode()


def read_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        payload = json.loads(urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(payload["at"]), UUID(payload["id"])
    except Exception:
        raise ApiError(
            400, "bad_cursor", "that cursor did not come from this list"
        ) from None


def owned_run(db: SessionDep, org_id: UUID, run_id: UUID) -> Run:
    found = db.execute(
        select(Run).where(Run.id == run_id, Run.org_id == org_id)
    ).scalar_one_or_none()
    if found is None:
        raise ApiError(404, "run_not_found", "no such Run")
    return found


@router.get(
    "/api/runs/{run_id}",
    operation_id="getRun",
    responses=errors(400, 401, 403, 404),
)
def get_run(run_id: UUID, member: ActiveMembership, db: SessionDep) -> RunDetail:
    """The persisted state a reconnect needs, in one payload."""
    run = owned_run(db, member.org_id, run_id)
    results = db.execute(
        select(StepResult)
        .where(StepResult.run_id == run_id)
        .order_by(StepResult.position, StepResult.id)
    ).scalars()
    intervals = db.execute(
        select(RunControlInterval)
        .where(RunControlInterval.run_id == run_id)
        .order_by(RunControlInterval.started_at, RunControlInterval.id)
    ).scalars()
    return RunDetail(
        run=run_record(run),
        step_results=[step_result_record(result) for result in results],
        control_intervals=[interval_record(interval) for interval in intervals],
        artifacts=[],
        batch_row=None,
    )


@router.get(
    "/api/runs/{run_id}/events",
    operation_id="streamRunEvents",
    response_class=StreamingResponse,
    responses={
        **errors(400, 401, 403, 404),
        200: {
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
            "description": "Live Run events. Reconnection replays nothing.",
        },
    },
)
def stream_run_events(
    run_id: UUID, member: ActiveMembership, db: SessionDep
) -> StreamingResponse:
    """Fan out `run:{id}:events` after the Organization gate; never replay."""
    owned_run(db, member.org_id, run_id)
    pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(events_channel(run_id))
    return StreamingResponse(
        fan_out(pubsub),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def fan_out(pubsub: Any) -> Iterator[str]:
    """Yield SSE frames until the client hangs up. Comments keep the socket alive."""
    try:
        while True:
            message = pubsub.get_message(timeout=1.0)
            if message is None:
                yield ":\n\n"
                continue
            if message.get("type") != "message":
                continue
            raw = message["data"]
            if isinstance(raw, bytes):
                raw = raw.decode()
            body = json.loads(raw)
            event_type = body.pop("type")
            yield f"event: {event_type}\ndata: {json.dumps(body)}\n\n"
    finally:
        pubsub.unsubscribe()
        pubsub.close()


@router.get(
    "/api/runs/{run_id}/logs",
    operation_id="listRunLogs",
    response_model_exclude_none=True,
    responses=errors(400, 401, 403, 404),
)
def list_run_logs(
    run_id: UUID,
    member: ActiveMembership,
    db: SessionDep,
    after_seq: int | None = None,
    step_id: UUID | None = None,
) -> list[LogLine]:
    """The persisted log, optionally after a seq or for one Step."""
    owned_run(db, member.org_id, run_id)
    conditions = [RunLogLine.run_id == run_id]
    if after_seq is not None:
        conditions.append(RunLogLine.seq > after_seq)
    if step_id is not None:
        conditions.append(RunLogLine.step_id == step_id)
    rows = db.execute(
        select(RunLogLine).where(*conditions).order_by(RunLogLine.seq)
    ).scalars()
    return [
        LogLine(
            seq=row.seq,
            step_id=row.step_id,
            level=row.level,
            text=row.text,
            at=row.at,
        )
        for row in rows
    ]


@router.post(
    "/api/runs/{run_id}/cancel",
    operation_id="cancelRun",
    status_code=202,
    responses=errors(400, 401, 403, 404, 409),
)
def cancel_run(run_id: UUID, member: ActiveMembership, db: SessionDep) -> Response:
    """Cancel queued or waiting work now; stamp a request on a running Run."""
    run = owned_run(db, member.org_id, run_id)
    if run.status.value not in NON_TERMINAL:
        raise ApiError(409, "run_terminal", "this Run has already ended")
    if run.status is RunStatus.QUEUED:
        run.status = RunStatus.CANCELLED
        run.ended_at = clock.now()
        db.commit()
        return Response(status_code=202)
    if run.status is RunStatus.WAITING_FOR_HUMAN:
        close_waiting_run(db, run, clock.now(), status=RunStatus.CANCELLED)
        db.commit()
        return Response(status_code=202)
    if run.cancel_requested_at is None:
        run.cancel_requested_at = clock.now()
    db.commit()
    get_redis().publish(control_channel(run.id), json.dumps({"cancel_requested": True}))
    return Response(status_code=202)


@router.post(
    "/api/runs/{run_id}/pause",
    operation_id="pauseRun",
    status_code=202,
    responses=errors(400, 401, 403, 404, 409),
)
def pause_run(run_id: UUID, member: ActiveMembership, db: SessionDep) -> Response:
    """Request takeover at the next safe boundary. Status stays running."""
    run = owned_run(db, member.org_id, run_id)
    if run.status.value not in NON_TERMINAL:
        raise ApiError(409, "run_terminal", "this Run has already ended")
    if run.pause_requested_at is None:
        run.pause_requested_at = clock.now()
    db.commit()
    get_redis().publish(control_channel(run.id), json.dumps({"pause_requested": True}))
    return Response(status_code=202)


def caller_session(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "unauthenticated", "no session")
    return token_digest(token)


@router.post(
    "/api/runs/{run_id}/takeover",
    operation_id="takeOverRun",
    responses=errors(400, 401, 403, 404, 409),
)
def take_over_run(
    run_id: UUID, request: Request, member: ActiveMembership, db: SessionDep
) -> TakeoverTicket:
    """Mint a control ticket for a waiting Run. One session holds it at a time."""
    run = owned_run(db, member.org_id, run_id)
    if run.status is not RunStatus.WAITING_FOR_HUMAN:
        raise ApiError(409, "not_waiting", "this Run is not waiting for a person")
    session_id = caller_session(request)
    holder = run.takeover_holder_session_id
    if holder is not None and holder != session_id:
        raise ApiError(409, "already_held", "another session already holds control")
    run.takeover_holder_session_id = session_id
    ticket, expires_at = mint_ticket(db, run.id, session_id)
    db.commit()
    return TakeoverTicket(
        ticket=ticket,
        ws_url=f"/api/runs/{run.id}/vnc?ticket={ticket}",
        expires_at=expires_at,
        deadline_at=run.takeover_deadline_at,
    )


@router.post(
    "/api/runs/{run_id}/handback",
    operation_id="handBackRun",
    status_code=202,
    responses=errors(400, 401, 403, 404, 409),
)
def hand_back_run(
    run_id: UUID, request: Request, member: ActiveMembership, db: SessionDep
) -> Response:
    """Ask the Worker to resume after a manual hand-back."""
    run = owned_run(db, member.org_id, run_id)
    if run.status is not RunStatus.WAITING_FOR_HUMAN:
        raise ApiError(409, "not_waiting", "this Run is not waiting for a person")
    if run.takeover_holder_session_id != caller_session(request):
        raise ApiError(409, "not_held", "this session does not hold control")
    if run.handback_requested_at is None:
        run.handback_requested_at = clock.now()
    db.commit()
    get_redis().publish(control_channel(run.id), json.dumps({"handback": True}))
    return Response(status_code=202)


@router.post(
    "/api/runs/{run_id}/takeover/abandon",
    operation_id="abandonTakeover",
    status_code=202,
    responses=errors(400, 401, 403, 404, 409),
)
def abandon_takeover(
    run_id: UUID, member: ActiveMembership, db: SessionDep
) -> Response:
    """Give up during takeover: the Run fails and the browser can close."""
    run = owned_run(db, member.org_id, run_id)
    if run.status is not RunStatus.WAITING_FOR_HUMAN:
        raise ApiError(409, "not_waiting", "this Run is not waiting for a person")
    close_waiting_run(
        db,
        run,
        clock.now(),
        status=RunStatus.FAILED,
        failure_reason=FailureReason.TAKEOVER_ABANDONED,
        fail_paused=True,
    )
    db.commit()
    return Response(status_code=202)


def run_summary(run: Run) -> RunSummary:
    return RunSummary(
        id=run.id,
        workflow_id=run.workflow_id,
        version_number=run.version_number,
        trigger=run.trigger,
        status=run.status,
        failure_reason=run.failure_reason,
        queued_at=run.queued_at,
        started_at=run.started_at,
        ended_at=run.ended_at,
    )


def run_record(run: Run) -> RunRecord:
    return RunRecord(
        id=run.id,
        workflow_id=run.workflow_id,
        version_number=run.version_number,
        draft_snapshot=run.draft_snapshot,
        is_test=run.is_test,
        trigger=run.trigger,
        status=run.status,
        failure_reason=run.failure_reason,
        failure_detail=run.failure_detail,
        variables=run.variables,
        timeout_ms=run.timeout_ms,
        worker_id=run.worker_id,
        worker_vnc_endpoint=run.worker_vnc_endpoint,
        heartbeat_at=run.heartbeat_at,
        cancel_requested_at=run.cancel_requested_at,
        pause_requested_at=run.pause_requested_at,
        takeover_deadline_at=run.takeover_deadline_at,
        auto_handback_disabled=run.auto_handback_disabled,
        queued_at=run.queued_at,
        started_at=run.started_at,
        ended_at=run.ended_at,
        automation_ms=run.automation_ms,
    )


def step_result_record(result: StepResult) -> StepResultRecord:
    return StepResultRecord(
        id=result.id,
        step_id=result.step_id,
        position=result.position,
        status=result.status,
        started_at=result.started_at,
        ended_at=result.ended_at,
        matched_candidate_rank=result.matched_candidate_rank,
        candidate_count=result.candidate_count,
        completed_by_human=result.completed_by_human,
        error_code=result.error_code,
        error_message=result.error_message,
        diagnostics=result.diagnostics,
        extracted_value=result.extracted_value,
    )


def interval_record(interval: RunControlInterval) -> ControlIntervalRecord:
    return ControlIntervalRecord(
        id=interval.id,
        kind=interval.kind,
        started_at=interval.started_at,
        ended_at=interval.ended_at,
    )
