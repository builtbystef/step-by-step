"""Execute one claimed Run in a fresh browser and persist what happened.

The executor knows the Workflow document and the rows it writes, but not how a
Run reached it. Dispatch supplies a claimed :class:`RunWork`; the store protocol
keeps each Step Result durable before the next Step can touch the page.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic
from typing import Any, Protocol
from uuid import UUID

from playwright.sync_api import BrowserType, Page
from playwright.sync_api import Error as PlaywrightError
from step_by_step_core.document import (
    REFERENCE,
    ClickStep,
    DownloadStep,
    DurationWaitPayload,
    ElementWaitPayload,
    ExtractStep,
    ListExtractPayload,
    NavigateStep,
    ScalarExtractPayload,
    SelectStep,
    Step,
    TakeoverStep,
    TypeStep,
    WaitStep,
    WorkflowDocument,
)

from step_by_step_worker.control import ControlFlags, RunCancelled
from step_by_step_worker.heartbeat import RunTerminal
from step_by_step_worker.selectors import Deadline, Resolved, SelectorFailure, resolve

log = getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class RunWork:
    """Everything execution needs from a Run and its Workflow."""

    run_id: UUID
    document: WorkflowDocument
    default_step_timeout_ms: int
    timeout_ms: int
    variables: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class StepOutcome:
    """One complete Step Result, ready to become a durable row."""

    step_id: UUID
    position: int
    status: str
    started_at: datetime | None
    ended_at: datetime
    matched_candidate_rank: int | None = None
    candidate_count: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    extracted_value: Any | None = None


class ResultStore(Protocol):
    """The Worker-side persistence boundary used during one Run."""

    def start_interval(self, run_id: UUID, kind: str, at: datetime) -> object: ...

    def end_interval(self, handle: object, at: datetime) -> None: ...

    def add_result(self, run_id: UUID, result: StepOutcome) -> None: ...

    def finish_run(
        self,
        run_id: UUID,
        status: str,
        failure_reason: str | None,
        failure_detail: str | None,
        automation_ms: int,
        at: datetime,
    ) -> None: ...

    def emit(
        self, run_id: UUID, event_type: str, payload: Mapping[str, Any]
    ) -> None: ...

    def log(
        self,
        run_id: UUID,
        level: str,
        text: str,
        step_id: UUID | None = None,
    ) -> None: ...


def now() -> datetime:
    return datetime.now(UTC)


def execute(
    work: RunWork,
    browser_type: BrowserType,
    store: ResultStore,
    profile_root: Path,
    *,
    headless: bool = False,
    heartbeat: Callable[[], None] | None = None,
    heartbeat_every: float = HEARTBEAT_INTERVAL_SECONDS,
    control: Callable[[], ControlFlags] | None = None,
) -> None:
    """Drive every Step in one claimed Run and leave no browser profile behind."""
    run_started = now()
    clock_started = monotonic()
    interval = store.start_interval(work.run_id, "automation", run_started)
    terminal_status = "succeeded"
    failure_reason: str | None = None
    failure_detail: str | None = None
    stop = Event()
    lost = Event()
    context_holder: list[Any] = []
    watcher = start_heartbeat(heartbeat, heartbeat_every, stop, lost, context_holder)

    def check_control(*_: object) -> None:
        if control is not None and control().cancel_requested:
            raise RunCancelled

    with TemporaryDirectory(prefix=f"run-{work.run_id}-", dir=profile_root) as profile:
        try:
            context = browser_type.launch_persistent_context(profile, headless=headless)
            context_holder.append(context)
        except PlaywrightError as error:
            terminal_status = "failed"
            failure_reason = "startup_failed"
            failure_detail = str(error)
            _skip_remaining(work, store, 0)
        else:
            try:
                page = context.pages[0] if context.pages else context.new_page()
                for position, step in enumerate(work.document.steps):
                    if lost.is_set():
                        break
                    try:
                        check_control()
                    except RunCancelled:
                        terminal_status = "cancelled"
                        _skip_remaining(work, store, position)
                        break
                    elapsed_ms = int((monotonic() - clock_started) * 1000)
                    if elapsed_ms >= work.timeout_ms:
                        terminal_status = "failed"
                        failure_reason = "run_timeout"
                        failure_detail = "the Run exhausted its automation timeout"
                        _skip_remaining(work, store, position)
                        break

                    announce_started(store, work, step, position)
                    try:
                        outcome = execute_step(
                            page,
                            step,
                            position,
                            work.default_step_timeout_ms,
                            work.variables,
                            on_control=check_control,
                        )
                    except RunCancelled:
                        terminal_status = "cancelled"
                        _skip_remaining(work, store, position)
                        break
                    if lost.is_set():
                        break
                    store.add_result(work.run_id, outcome)
                    announce_finished(store, work, outcome)
                    if outcome.status == "failed":
                        terminal_status = "failed"
                        failure_reason = "step_failed"
                        failure_detail = outcome.error_message
                        _skip_remaining(work, store, position + 1)
                        break
                    try:
                        check_control()
                    except RunCancelled:
                        terminal_status = "cancelled"
                        _skip_remaining(work, store, position + 1)
                        break
                    elapsed_ms = int((monotonic() - clock_started) * 1000)
                    if elapsed_ms >= work.timeout_ms:
                        terminal_status = "failed"
                        failure_reason = "run_timeout"
                        failure_detail = "the Run exhausted its automation timeout"
                        _skip_remaining(work, store, position + 1)
                        break
            finally:
                close_quietly(context)

    stop.set()
    if watcher is not None:
        watcher.join(timeout=heartbeat_every + 1)
    if lost.is_set():
        # A 409 means the row is already terminal; do not overwrite it.
        store.end_interval(interval, now())
        return

    ended_at = now()
    automation_ms = int((monotonic() - clock_started) * 1000)
    store.end_interval(interval, ended_at)
    store.finish_run(
        work.run_id,
        terminal_status,
        failure_reason,
        failure_detail,
        automation_ms,
        ended_at,
    )
    status_payload: dict[str, Any] = {
        "run_id": work.run_id,
        "status": terminal_status,
        "at": ended_at,
    }
    if failure_reason is not None:
        status_payload["failure_reason"] = failure_reason
    if failure_detail is not None:
        status_payload["failure_detail"] = failure_detail
    store.emit(work.run_id, "run.status", status_payload)


def start_heartbeat(
    heartbeat: Callable[[], None] | None,
    every: float,
    stop: Event,
    lost: Event,
    context_holder: list[Any],
) -> Thread | None:
    """Beat in the background; a terminal Run closes the browser from this thread."""
    if heartbeat is None:
        return None

    def watch() -> None:
        while not stop.wait(every):
            try:
                heartbeat()
            except RunTerminal:
                lost.set()
                if context_holder:
                    close_quietly(context_holder[0])
                return
            except Exception:
                log.exception("heartbeat failed")

    watcher = Thread(target=watch, name="run-heartbeat", daemon=True)
    watcher.start()
    return watcher


def close_quietly(context: Any) -> None:
    try:
        context.close()
    except Exception:
        return


def _skip_remaining(work: RunWork, store: ResultStore, start: int) -> None:
    at = now()
    for position, step in enumerate(work.document.steps[start:], start=start):
        outcome = StepOutcome(
            step_id=step.id,
            position=position,
            status="skipped",
            started_at=None,
            ended_at=at,
        )
        store.add_result(work.run_id, outcome)
        announce_finished(store, work, outcome)


def announce_started(
    store: ResultStore, work: RunWork, step: Step, position: int
) -> None:
    at = now()
    store.emit(
        work.run_id,
        "step.started",
        {
            "run_id": work.run_id,
            "step_id": step.id,
            "position": position,
            "at": at,
        },
    )
    store.log(work.run_id, "info", step.label, step_id=step.id)


def announce_finished(store: ResultStore, work: RunWork, outcome: StepOutcome) -> None:
    payload: dict[str, Any] = {
        "run_id": work.run_id,
        "step_id": outcome.step_id,
        "status": outcome.status,
        "matched_candidate_rank": outcome.matched_candidate_rank,
        "candidate_count": outcome.candidate_count,
        "completed_by_human": False,
        "at": outcome.ended_at,
    }
    extracted = extracted_count(outcome.extracted_value)
    if extracted is not None:
        payload["extracted_count"] = extracted
    store.emit(work.run_id, "step.finished", payload)


def extracted_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, list):
        return len(value)
    return 1


def execute_step(
    page: Page,
    step: Step,
    position: int,
    default_timeout_ms: int,
    variables: Mapping[str, Any],
    on_control: Callable[..., None] | None = None,
) -> StepOutcome:
    """Execute one Step, returning only after its observable outcome is complete."""
    started_at = now()
    if step.disabled:
        return StepOutcome(step.id, position, "skipped", None, started_at)

    deadline = Deadline.in_ms(step.timeout_ms or default_timeout_ms)
    try:
        matched, extracted = perform(page, step, deadline, variables, on_control)
    except StepFailure as failure:
        status = "skipped" if step.optional and failure.target_missing else "failed"
        return StepOutcome(
            step_id=step.id,
            position=position,
            status=status,
            started_at=started_at,
            ended_at=now(),
            candidate_count=failure.candidate_count,
            error_code=None if status == "skipped" else failure.code,
            error_message=None if status == "skipped" else failure.message,
        )
    except PlaywrightError as error:
        return StepOutcome(
            step_id=step.id,
            position=position,
            status="failed",
            started_at=started_at,
            ended_at=now(),
            error_code="action_failed",
            error_message=str(error),
        )

    return StepOutcome(
        step_id=step.id,
        position=position,
        status="passed",
        started_at=started_at,
        ended_at=now(),
        matched_candidate_rank=matched.rank if matched else None,
        candidate_count=matched.candidate_count if matched else None,
        extracted_value=extracted,
    )


@dataclass(frozen=True, slots=True)
class StepFailure(Exception):
    code: str
    message: str
    target_missing: bool = False
    candidate_count: int | None = None


def resolved(
    page: Page,
    target: Any,
    deadline: Deadline,
    on_walk: Callable[..., None] | None = None,
) -> Resolved:
    result = resolve(page, target, deadline, on_walk=on_walk)
    if isinstance(result, SelectorFailure):
        raise StepFailure(
            code=result.reason.value,
            message=result.message,
            target_missing=True,
            candidate_count=result.candidate_count,
        )
    return result


def perform(
    page: Page,
    step: Step,
    deadline: Deadline,
    variables: Mapping[str, Any],
    on_control: Callable[..., None] | None = None,
) -> tuple[Resolved | None, Any | None]:
    """Perform the action named by one parsed Step."""
    if isinstance(step, NavigateStep):
        page.goto(
            interpolate(step.payload.url, variables), timeout=deadline.remaining_ms
        )
        return None, None
    if isinstance(step, ClickStep):
        found = resolved(page, step.payload.target, deadline, on_control)
        if step.payload.asserted_navigation:
            with page.expect_navigation(timeout=deadline.remaining_ms):
                found.locator.click(timeout=deadline.remaining_ms)
        else:
            found.locator.click(timeout=deadline.remaining_ms)
        return found, None
    if isinstance(step, TypeStep):
        found = resolved(page, step.payload.target, deadline, on_control)
        found.locator.fill(
            interpolate(step.payload.value, variables), timeout=deadline.remaining_ms
        )
        return found, None
    if isinstance(step, SelectStep):
        found = resolved(page, step.payload.target, deadline, on_control)
        found.locator.select_option(step.payload.value, timeout=deadline.remaining_ms)
        return found, None
    if isinstance(step, DownloadStep):
        found = resolved(page, step.payload.target, deadline, on_control)
        with page.expect_download(timeout=deadline.remaining_ms):
            found.locator.click(timeout=deadline.remaining_ms)
        return found, None
    if isinstance(step, ExtractStep):
        found = resolved(page, step.payload.target, deadline, on_control)
        if isinstance(step.payload, ScalarExtractPayload):
            value = (
                found.locator.get_attribute(
                    step.payload.attribute, timeout=deadline.remaining_ms
                )
                if step.payload.attribute
                else found.locator.text_content(timeout=deadline.remaining_ms)
            )
            return found, value
        if isinstance(step.payload, ListExtractPayload):
            rows: list[dict[str, str | None]] = []
            for index in range(found.locator.count()):
                item = found.locator.nth(index)
                rows.append(
                    {
                        field.name: (
                            item.locator(field.sub_selector).get_attribute(
                                field.attribute, timeout=deadline.remaining_ms
                            )
                            if field.attribute
                            else item.locator(field.sub_selector).text_content(
                                timeout=deadline.remaining_ms
                            )
                        )
                        for field in step.payload.fields
                    }
                )
            return found, rows
    if isinstance(step, WaitStep):
        if isinstance(step.payload, DurationWaitPayload):
            if step.payload.duration_ms > deadline.remaining_ms:
                page.wait_for_timeout(deadline.remaining_ms)
                raise StepFailure("step_timeout", "the wait exceeded the Step timeout")
            page.wait_for_timeout(step.payload.duration_ms)
            return None, None
        if isinstance(step.payload, ElementWaitPayload):
            return resolved(page, step.payload.target, deadline, on_control), None
    if isinstance(step, TakeoverStep):
        raise StepFailure(
            "takeover_not_available",
            "pause-for-takeover is owned by the Run control slice",
        )
    raise AssertionError(f"unhandled Step type: {step.type}")


def interpolate(value: str, variables: Mapping[str, Any]) -> str:
    """Substitute the declared Run values in navigate and type strings."""
    return REFERENCE.sub(
        lambda reference: str(variables.get(reference.group(1), reference.group(0))),
        value,
    )
