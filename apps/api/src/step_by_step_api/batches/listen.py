"""Consume terminal run.status events so a Batch advances without a tick."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from uuid import UUID

from step_by_step_core.bus import get_redis
from step_by_step_core.events import TERMINAL_CHANNEL

from step_by_step_api.batches.advance import on_terminal_run

log = logging.getLogger(__name__)


def listen_forever() -> None:
    """Block on `runs:terminal` and advance the Batch that Run belongs to."""
    pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(TERMINAL_CHANNEL)
    for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        raw = message["data"]
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            body = json.loads(raw)
            on_terminal_run(UUID(body["run_id"]))
        except Exception:
            log.exception("batch advance from terminal event failed")


def start_in_lifespan() -> asyncio.Task[None] | None:
    """Begin the subscriber unless a test run is driving the app itself."""
    if os.environ.get("PYTEST_VERSION") is not None:
        return None
    return asyncio.create_task(asyncio.to_thread(listen_forever))
