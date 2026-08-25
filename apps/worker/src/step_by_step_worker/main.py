"""The long-lived Worker: prove readiness, then claim and execute Runs serially."""

import logging
import signal
import threading
from os import environ
from pathlib import Path

from playwright.sync_api import sync_playwright
from step_by_step_core.bus import get_redis

from step_by_step_worker.checks import STARTUP_CHECKS, worker_id
from step_by_step_worker.dispatch import work_once
from step_by_step_worker.readiness import report
from step_by_step_worker.store import PostgresRunStore


def consume(log: logging.Logger) -> None:
    """Keep one browser-owning Run at a time on this Worker until shutdown."""
    stopping = threading.Event()
    for asked in (signal.SIGTERM, signal.SIGINT):
        signal.signal(asked, lambda *_: stopping.set())

    identity = worker_id()
    vnc_endpoint = environ.get("WORKER_VNC_ENDPOINT") or (
        f"{identity}:{environ.get('VNC_PORT', '5900')}"
    )
    profile_root = Path(environ.get("WORKER_PROFILE_ROOT", "/tmp/step-by-step-runs"))
    profile_root.mkdir(parents=True, exist_ok=True)
    store = PostgresRunStore()

    with sync_playwright() as driver:
        while not stopping.is_set():
            worked = work_once(
                get_redis(),
                store,
                driver.chromium,
                profile_root,
                worker_id=identity,
                vnc_endpoint=vnc_endpoint,
                follow_control=True,
            )
            if worked:
                log.info("Run finished; waiting for the next one")
    log.info("stopping")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s"
    )
    log = logging.getLogger(f"worker.{worker_id()}")

    log.info("starting")
    report(STARTUP_CHECKS, log)
    log.info("ready — waiting for Runs")
    consume(log)


if __name__ == "__main__":
    main()
