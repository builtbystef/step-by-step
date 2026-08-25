"""The backend's minute loop.

One directly-invokable `tick` is the whole surface: it fires due Schedules,
reaps stale-heartbeat Runs, times out over-deadline takeovers, and re-enqueues
queued Runs the dispatch list dropped. Tests call `tick()` themselves. The
process starts the minute waiter from the app lifespan.
"""

from __future__ import annotations

import asyncio
import logging
import os

from step_by_step_core.bus import DISPATCH_LIST, get_redis
from step_by_step_core.db import session_scope

from step_by_step_api import clock
from step_by_step_api.runs.reap import reap_and_backstop
from step_by_step_api.schedules.fire import fire_due_schedules

log = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = 60


def tick() -> None:
    """One pass of the loop. Safe to call from a test without waiting a minute."""
    with session_scope() as db:
        now = clock.now()
        run_ids = fire_due_schedules(db, now)
        run_ids.extend(reap_and_backstop(db, now))
        db.commit()
    if not run_ids:
        return
    redis = get_redis()
    for run_id in run_ids:
        redis.lpush(DISPATCH_LIST, str(run_id))


async def run_forever() -> None:
    """Sleep a minute, tick, repeat. Failures are logged; the loop stays up."""
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("minute loop tick failed")


def start_in_lifespan() -> asyncio.Task[None] | None:
    """Begin the waiter unless a test run is driving the app itself."""
    if os.environ.get("PYTEST_VERSION") is not None:
        return None
    return asyncio.create_task(run_forever())
