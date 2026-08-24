"""Claim Run ids from Redis and hand exactly one claimed Run to the executor."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from playwright.sync_api import BrowserType
from step_by_step_core.bus import DISPATCH_LIST

from step_by_step_worker.executor import ResultStore, RunWork, execute


class DispatchQueue(Protocol):
    def brpop(self, keys: str, timeout: int) -> Any: ...


class RunStore(ResultStore, Protocol):
    def claim(
        self,
        run_id: UUID,
        worker_id: str,
        vnc_endpoint: str,
        at: datetime,
    ) -> RunWork | None: ...


def work_once(
    queue: DispatchQueue,
    store: RunStore,
    browser_type: BrowserType,
    profile_root: Path,
    *,
    worker_id: str,
    vnc_endpoint: str,
    headless: bool = False,
    pop_timeout: int = 1,
) -> bool:
    """Execute the next claimable id, dropping stale ids along the way.

    ``False`` means the blocking pop timed out. An id that was cancelled or was
    already claimed is not work and does not make the Worker pause before the
    next pop.
    """
    while popped := queue.brpop(DISPATCH_LIST, timeout=pop_timeout):
        raw_id = popped[1]
        if isinstance(raw_id, bytes):
            raw_id = raw_id.decode()
        try:
            run_id = UUID(str(raw_id))
        except ValueError:
            continue
        work = store.claim(
            run_id,
            worker_id=worker_id,
            vnc_endpoint=vnc_endpoint,
            at=datetime.now(UTC),
        )
        if work is None:
            continue
        execute(work, browser_type, store, profile_root, headless=headless)
        return True
    return False
