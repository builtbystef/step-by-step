"""Worker → backend routes for a live Run. Shared compose token, no session."""

from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import select

from step_by_step_api import clock
from step_by_step_api.auth_states.blob import AuthStateBlob
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError
from step_by_step_api.internal import InternalToken
from step_by_step_api.runs.credentials import (
    ConsentedDomains,
    Credentials,
    consented_domains,
    credentials_for,
    write_auth_states,
)
from step_by_step_api.runs.models import (
    Run,
    RunControlInterval,
    RunControlKind,
    RunStatus,
)

router = APIRouter(include_in_schema=False)

LIVE = (RunStatus.RUNNING, RunStatus.WAITING_FOR_HUMAN)


class Heartbeat(BaseModel):
    worker_id: str
    vnc_endpoint: str


class RunControl(BaseModel):
    cancel_requested: bool
    pause_requested: bool
    takeover_phase: str | None
    auto_handback_disabled: bool


class AuthStateWriteBack(BaseModel):
    states: list[AuthStateBlob] = []
    new_candidates: list[str] = []


def live_assigned_run(db: SessionDep, run_id: UUID) -> Run:
    """The Run a Worker may still act on: assigned, and not yet terminal."""
    run = db.get(Run, run_id)
    if run is None or run.status not in LIVE or run.worker_id is None:
        raise ApiError(409, "run_terminal", "the Run is no longer this Worker's")
    return run


@router.get("/internal/runs/{run_id}/control")
def control(run_id: UUID, db: SessionDep, _: InternalToken) -> RunControl:
    """The row's request flags. The Worker re-reads these at every boundary."""
    run = db.get(Run, run_id)
    if run is None:
        raise ApiError(404, "run_not_found", "no such Run")
    return RunControl(
        cancel_requested=run.cancel_requested_at is not None,
        pause_requested=run.pause_requested_at is not None,
        takeover_phase=open_takeover_phase(db, run_id),
        auto_handback_disabled=run.auto_handback_disabled,
    )


def open_takeover_phase(db: SessionDep, run_id: UUID) -> str | None:
    """The open control interval's kind, when it is not automation."""
    interval = db.execute(
        select(RunControlInterval)
        .where(
            RunControlInterval.run_id == run_id,
            RunControlInterval.ended_at.is_(None),
        )
        .order_by(RunControlInterval.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if interval is None or interval.kind is RunControlKind.AUTOMATION:
        return None
    return interval.kind.value


@router.post("/internal/runs/{run_id}/heartbeat", status_code=204)
def heartbeat(
    run_id: UUID,
    body: Heartbeat,
    db: SessionDep,
    _: InternalToken,
) -> Response:
    """Stamp the Run's liveness. A terminal Run tells the Worker to stop."""
    run = live_assigned_run(db, run_id)
    run.heartbeat_at = clock.now()
    run.worker_id = body.worker_id
    run.worker_vnc_endpoint = body.vnc_endpoint
    db.commit()
    return Response(status_code=204)


@router.get("/internal/runs/{run_id}/credentials")
def credentials(run_id: UUID, db: SessionDep, _: InternalToken) -> Credentials:
    """Resolved plaintext for this Run. The body must never be logged."""
    return credentials_for(db, live_assigned_run(db, run_id))


@router.get("/internal/runs/{run_id}/auth-state-consents")
def auth_state_consents(
    run_id: UUID, db: SessionDep, _: InternalToken
) -> ConsentedDomains:
    live_assigned_run(db, run_id)
    return ConsentedDomains(domains=consented_domains(db, run_id))


@router.post("/internal/runs/{run_id}/auth-states", status_code=204)
def auth_states(
    run_id: UUID,
    body: AuthStateWriteBack,
    db: SessionDep,
    _: InternalToken,
) -> Response:
    run = live_assigned_run(db, run_id)
    write_auth_states(db, run, body.states, body.new_candidates)
    db.commit()
    return Response(status_code=204)
