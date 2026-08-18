"""What a Worker proves before it will take a Run.

A Worker with no Redis, no Postgres, no display, no VNC server, or no reachable
Artifact store cannot execute a Run, and a Worker that idles anyway is worse
than one that is absent: the pool counts it. So every check runs at startup,
each says what it found, and a single failure stops the process.
"""

import logging
from collections.abc import Callable, Mapping

type Check = Callable[[], str]
"""A check returns what it found, or raises to say what went wrong."""


class NotReady(RuntimeError):
    """A Worker failed a startup check and must not join the pool."""


def report(checks: Mapping[str, Check], log: logging.Logger | None = None) -> None:
    """Run every check, log what each one found, and raise if any failed.

    Every check runs even after one has failed, so that one boot shows an
    operator every problem rather than one problem per boot.
    """
    log = log or logging.getLogger(__name__)
    failed: list[str] = []

    for name, check in checks.items():
        try:
            log.info("%s: %s", name, check())
        # Any failure at all is a failed check — the process must not start.
        except Exception as reason:
            log.error("%s: %s", name, reason)
            failed.append(name)

    if failed:
        raise NotReady(f"failed startup checks: {', '.join(failed)}")
