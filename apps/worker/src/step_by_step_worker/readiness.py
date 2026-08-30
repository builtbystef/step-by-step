import logging
from collections.abc import Callable, Mapping

type Check = Callable[[], str]


class NotReady(RuntimeError):
    pass


def report(checks: Mapping[str, Check], log: logging.Logger | None = None) -> None:
    log = log or logging.getLogger(__name__)
    failed: list[str] = []

    for name, check in checks.items():
        try:
            log.info("%s: %s", name, check())
        except Exception as reason:
            log.error("%s: %s", name, reason)
            failed.append(name)

    if failed:
        raise NotReady(f"failed startup checks: {', '.join(failed)}")
