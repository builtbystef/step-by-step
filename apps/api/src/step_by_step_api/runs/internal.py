"""Worker → backend routes for a live Run. Shared compose token, no session."""

from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel

from step_by_step_api import clock
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError
from step_by_step_api.internal import InternalToken
from step_by_step_api.runs.models import Run, RunStatus

router = APIRouter(include_in_schema=False)

LIVE = (RunStatus.RUNNING, RunStatus.WAITING_FOR_HUMAN)


class Heartbeat(BaseModel):
    worker_id: str
    vnc_endpoint: str


@router.post("/internal/runs/{run_id}/heartbeat", status_code=204)
def heartbeat(
    run_id: UUID,
    body: Heartbeat,
    db: SessionDep,
    _: InternalToken,
) -> Response:
    """Stamp the Run's liveness. A terminal Run tells the Worker to stop."""
    run = db.get(Run, run_id)
    if run is None or run.status not in LIVE or run.worker_id is None:
        raise ApiError(409, "run_terminal", "the Run is no longer this Worker's")
    run.heartbeat_at = clock.now()
    run.worker_id = body.worker_id
    run.worker_vnc_endpoint = body.vnc_endpoint
    db.commit()
    return Response(status_code=204)
