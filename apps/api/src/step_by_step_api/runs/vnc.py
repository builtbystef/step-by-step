"""The WebSocket that pipes RFB between a browser and a Worker's VNC server."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from os import environ
from uuid import UUID

from fastapi import APIRouter, WebSocket
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect
from step_by_step_core.db import session_scope

from step_by_step_api.accounts.models import Session, User
from step_by_step_api.accounts.orgs import membership_in
from step_by_step_api.accounts.sessions import SESSION_COOKIE, token_digest
from step_by_step_api.errors import ApiError
from step_by_step_api.runs.models import NON_TERMINAL, Run
from step_by_step_api.runs.rfb import (
    RfbError,
    StreamPipe,
    WebsocketPipe,
    authenticate_as_client,
    offer_none,
)
from step_by_step_api.runs.tickets import redeem_ticket

router = APIRouter()

VNC_CONTROL_PASSWORD_VARIABLE = "VNC_CONTROL_PASSWORD"
VNC_VIEW_PASSWORD_VARIABLE = "VNC_VIEW_PASSWORD"
WATCH_INTERVAL = 0.25
"""How often an open proxy re-reads the Run to notice takeover ending."""


def vnc_passwords() -> tuple[str, str]:
    """Control and view-only passwords, shared across Workers."""
    control = environ.get(VNC_CONTROL_PASSWORD_VARIABLE, "")
    view = environ.get(VNC_VIEW_PASSWORD_VARIABLE, "")
    if not control or not view:
        raise ApiError(503, "vnc_unconfigured", "VNC passwords are not set")
    return control, view


def parse_endpoint(endpoint: str) -> tuple[str, int]:
    host, sep, port = endpoint.rpartition(":")
    if not sep:
        raise ValueError(f"not a host:port endpoint: {endpoint!r}")
    return host, int(port)


@router.websocket("/api/runs/{run_id}/vnc")
async def vnc_socket(websocket: WebSocket, run_id: UUID, ticket: str) -> None:
    """Validate the ticket, then pipe RFB. View-only unless this session holds."""
    control_password, view_password = vnc_passwords()
    with session_scope() as db:
        session_id, endpoint, control = admit(db, websocket, run_id, ticket)
        db.commit()
    password = control_password if control else view_password
    reader, writer = await connect_worker(endpoint, password)
    await websocket.accept()
    try:
        await offer_none(WebsocketPipe(websocket))
        await pipe_rfb(websocket, reader, writer, run_id, session_id, control)
    finally:
        writer.close()
        with suppress(OSError):
            await writer.wait_closed()
        with suppress(RuntimeError):
            await websocket.close()


def admit(db, websocket: WebSocket, run_id: UUID, ticket: str) -> tuple[str, str, bool]:
    """Spend the ticket and return (session_id, vnc endpoint, holds control).

    Another Organization's Run, a bad ticket, and a missing session are the
    same 404 — and none of them opens a socket to a Worker.
    """
    token = websocket.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "unauthenticated", "no session")
    session_id = token_digest(token)
    spent = redeem_ticket(db, ticket)
    if spent is None or spent.run_id != run_id or spent.session_id != session_id:
        raise ApiError(404, "run_not_found", "no such Run")
    user = db.execute(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(Session.token_hash == session_id)
    ).scalar_one_or_none()
    run = db.get(Run, run_id)
    if user is None or run is None or membership_in(db, user, run.org_id) is None:
        raise ApiError(404, "run_not_found", "no such Run")
    if run.status.value not in NON_TERMINAL or not run.worker_vnc_endpoint:
        raise ApiError(409, "run_terminal", "this Run has already ended")
    control = (
        run.takeover_holder_session_id == session_id
        and run.handback_requested_at is None
    )
    return session_id, run.worker_vnc_endpoint, control


async def connect_worker(endpoint: str, password: str):
    host, port = parse_endpoint(endpoint)
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except OSError as exc:
        raise ApiError(502, "vnc_unreachable", "the Worker is not reachable") from exc
    try:
        await authenticate_as_client(StreamPipe(reader, writer), password)
    except (RfbError, asyncio.IncompleteReadError) as exc:
        writer.close()
        raise ApiError(502, "vnc_unreachable", "the Worker is not reachable") from exc
    return reader, writer


async def pipe_rfb(
    websocket: WebSocket,
    reader,
    writer,
    run_id: UUID,
    session_id: str,
    control: bool,
) -> None:
    """Copy bytes both ways until the client, the Worker, or takeover ends."""

    async def to_worker() -> None:
        while True:
            data = await websocket.receive_bytes()
            writer.write(data)
            await writer.drain()

    async def to_client() -> None:
        while True:
            data = await reader.read(65536)
            if not data:
                return
            await websocket.send_bytes(data)

    async def watch() -> None:
        while still_open(run_id, session_id, control):
            await asyncio.sleep(WATCH_INTERVAL)

    tasks = [
        asyncio.create_task(to_worker()),
        asyncio.create_task(to_client()),
        asyncio.create_task(watch()),
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        exc = task.exception() if not task.cancelled() else None
        if exc is not None and not isinstance(exc, WebSocketDisconnect):
            raise exc


def still_open(run_id: UUID, session_id: str, control: bool) -> bool:
    """False once the Run ended, or a control connection lost the hold."""
    with session_scope() as db:
        run = db.get(Run, run_id)
        if run is None or run.status.value not in NON_TERMINAL:
            return False
        if not control:
            return True
        if run.takeover_holder_session_id != session_id:
            return False
        return run.handback_requested_at is None
