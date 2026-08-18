"""The Worker process.

It proves it can reach everything a Run needs, says so, and waits. There is no
dispatch and no executor yet: nothing pops a Run id, and nothing drives a
browser. Those arrive with the slices that own them.
"""

import logging
import signal
import threading

from step_by_step_worker.checks import STARTUP_CHECKS, worker_id
from step_by_step_worker.readiness import report


def idle(log: logging.Logger) -> None:
    """Hold the process open until the container is asked to stop."""
    stopping = threading.Event()
    for asked in (signal.SIGTERM, signal.SIGINT):
        signal.signal(asked, lambda *_: stopping.set())
    stopping.wait()
    log.info("stopping")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s"
    )
    log = logging.getLogger(f"worker.{worker_id()}")

    log.info("starting")
    report(STARTUP_CHECKS, log)
    log.info("ready — idle; there is no dispatch yet")

    idle(log)


if __name__ == "__main__":
    main()
