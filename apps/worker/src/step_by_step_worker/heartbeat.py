"""POST the shared-token heartbeat that keeps a claimed Run alive."""

from __future__ import annotations

import json
from collections.abc import Callable
from os import environ
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

INTERNAL_TOKEN_VARIABLE = "INTERNAL_TOKEN"
API_URL_VARIABLE = "API_URL"


class RunTerminal(Exception):
    """The Run is no longer this Worker's to execute."""


def post_heartbeat(run_id: UUID, worker_id: str, vnc_endpoint: str) -> None:
    """Stamp the Run row. Raises :class:`RunTerminal` on 409 `run_terminal`."""
    base = environ[API_URL_VARIABLE].rstrip("/")
    token = environ[INTERNAL_TOKEN_VARIABLE]
    request = Request(
        f"{base}/internal/runs/{run_id}/heartbeat",
        data=json.dumps(
            {"worker_id": worker_id, "vnc_endpoint": vnc_endpoint}
        ).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            response.read()
    except HTTPError as error:
        if error.code == 409:
            raise RunTerminal from error
        raise


def pulse(run_id: UUID, worker_id: str, vnc_endpoint: str) -> Callable[[], None]:
    """A zero-argument beat the executor can call on its interval."""

    def beat() -> None:
        post_heartbeat(run_id, worker_id, vnc_endpoint)

    return beat
