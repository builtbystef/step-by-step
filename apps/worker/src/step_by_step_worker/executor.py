"""Execute one claimed Run in a fresh browser and persist what happened.

The executor knows the Workflow document and the rows it writes, but not how a
Run reached it. Dispatch supplies a claimed :class:`RunWork`; the store protocol
keeps each Step Result durable before the next Step can touch the page.
"""

import mimetypes
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
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
    Target,
    TypeStep,
    WaitStep,
    WorkflowDocument,
)

from step_by_step_worker.challenge import page_shows_challenge
from step_by_step_worker.control import ControlFlags, RunCancelled, RunPaused
from step_by_step_worker.credentials import (
    Credentials,
    CredentialSet,
    MissingSecret,
    capture,
    existing_and_consented,
    inject,
)
from step_by_step_worker.heartbeat import RunTerminal
from step_by_step_worker.redact import RedactingStore
from step_by_step_worker.selectors import Deadline, Resolved, SelectorFailure, resolve

log = getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 5.0
DEFAULT_TAKEOVER_TIMEOUT_MS = 30 * 60 * 1000
PARK_POLL_SECONDS = 0.05
HAND_BACK_GRACE = timedelta(seconds=6)


@dataclass(frozen=True, slots=True)
class RunWork:
    """Everything execution needs from a Run and its Workflow."""

    run_id: UUID
    document: WorkflowDocument
    default_step_timeout_ms: int
    timeout_ms: int
    variables: Mapping[str, Any]
    takeover_timeout_ms: int = DEFAULT_TAKEOVER_TIMEOUT_MS


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
    completed_by_human: bool = False
    diagnostics: dict[str, Any] | None = None


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

    def park(self, run_id: UUID, deadline_at: datetime, at: datetime) -> None: ...

    def resume(self, run_id: UUID, at: datetime) -> None: ...

    def release_holder(self, run_id: UUID, at: datetime) -> None: ...

    def add_artifact(
        self,
        run_id: UUID,
        *,
        kind: str,
        body: bytes,
        content_type: str,
        index: int,
        step_id: UUID | None = None,
        filename: str = "",
    ) -> UUID: ...


@dataclass(frozen=True, slots=True)
class DownloadCapture:
    """The file a download Step produced, before it is stored as an Artifact."""

    filename: str
    content_type: str
    body: bytes


class TraceCapture:
    """Playwright tracing, with holes around secrets and takeover."""

    def __init__(
        self,
        context: Any,
        profile: str,
        store: ResultStore,
        work: RunWork,
    ) -> None:
        self._context = context
        self._profile = profile
        self._store = store
        self._work = work
        self._index = 0
        self._active = False
        self._reasons: set[str] = set()

    def start(self) -> None:
        self._context.tracing.start(snapshots=True, screenshots=True)
        self._active = True

    def pause(self, reason: str) -> None:
        self._reasons.add(reason)
        self._stop_current()

    def resume(self, reason: str) -> None:
        self._reasons.discard(reason)
        if not self._reasons:
            self._start_current()

    def finish(self) -> None:
        if self._active:
            self._save(final=True)
            self._active = False
            return
        try:
            self._context.tracing.stop()
        except Exception:
            log.exception("trace stop failed")

    def _stop_current(self) -> None:
        if not self._active:
            return
        self._save(final=False)
        self._active = False

    def _start_current(self) -> None:
        if self._active:
            return
        try:
            self._context.tracing.start_chunk()
        except Exception:
            log.exception("trace start failed")
            return
        self._active = True

    def _save(self, *, final: bool) -> None:
        save_trace_chunk(
            self._context,
            self._profile,
            self._store,
            self._work,
            self._index,
            final=final,
        )
        self._index += 1


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
    credentials: Credentials | None = None,
) -> None:
    """Drive every Step in one claimed Run and leave no browser profile behind."""
    run_started = now()
    automation_clock = monotonic()
    automation_ms = 0
    in_automation = True
    interval: list[object | None] = [
        store.start_interval(work.run_id, "automation", run_started)
    ]
    terminal_status = "succeeded"
    failure_reason: str | None = None
    failure_detail: str | None = None
    stop = Event()
    lost = Event()
    context_holder: list[Any] = []
    traces: list[TraceCapture | None] = [None]
    watcher = start_heartbeat(heartbeat, heartbeat_every, stop, lost, context_holder)

    def close_open(at: datetime) -> None:
        handle = interval[0]
        if handle is not None:
            store.end_interval(handle, at)
            interval[0] = None

    def open_kind(kind: str, at: datetime) -> None:
        interval[0] = store.start_interval(work.run_id, kind, at)

    def leave_automation(at: datetime) -> None:
        nonlocal automation_ms, in_automation
        if in_automation:
            automation_ms += int((monotonic() - automation_clock) * 1000)
            in_automation = False
        close_open(at)

    def enter_automation(at: datetime) -> None:
        nonlocal automation_clock, in_automation
        open_kind("automation", at)
        automation_clock = monotonic()
        in_automation = True

    def elapsed() -> int:
        running = int((monotonic() - automation_clock) * 1000) if in_automation else 0
        return automation_ms + running

    def emit_control(
        phase: str, at: datetime, deadline_at: datetime | None = None
    ) -> None:
        payload: dict[str, Any] = {
            "run_id": work.run_id,
            "phase": phase,
            "at": at,
        }
        if deadline_at is not None:
            payload["deadline_at"] = deadline_at
        store.emit(work.run_id, "control", payload)

    def emit_predicate(
        met: bool, at: datetime, grace_ends_at: datetime | None = None
    ) -> None:
        payload: dict[str, Any] = {
            "run_id": work.run_id,
            "met": met,
            "at": at,
        }
        if grace_ends_at is not None:
            payload["grace_ends_at"] = grace_ends_at
        store.emit(work.run_id, "predicate", payload)

    def park_for_human(
        timeout_ms: int, page: Page, success_check: Target | None
    ) -> str:
        capture = traces[0]
        if capture is not None:
            capture.pause("takeover")
        at = now()
        leave_automation(at)
        deadline_at = at + timedelta(milliseconds=timeout_ms)
        open_kind("waiting", at)
        store.park(work.run_id, deadline_at, at)
        emit_control("waiting", at, deadline_at)
        phase = "waiting"
        last_met: bool | None = None
        grace_ends_at: datetime | None = None

        def poll_check() -> bool | None:
            if success_check is None:
                return None
            return success_check_met(page, success_check)

        met = poll_check()
        if met is not None:
            emit_predicate(met, now())
            last_met = met

        while not lost.is_set():
            flags = control() if control is not None else ControlFlags()
            met = poll_check()
            if met is not None and met != last_met:
                last_met = met
                if not met:
                    grace_ends_at = None
                    emit_predicate(False, now())
                elif phase != "human":
                    emit_predicate(True, now())
            if flags.holder_present and phase == "waiting":
                at = now()
                close_open(at)
                open_kind("human", at)
                emit_control("human", at, deadline_at)
                phase = "human"
                grace_ends_at = None
            if phase == "human" and flags.auto_handback_disabled:
                if grace_ends_at is not None:
                    grace_ends_at = None
                    if met is True:
                        emit_predicate(True, now())
            elif (
                phase == "human"
                and met is True
                and not flags.auto_handback_disabled
                and grace_ends_at is None
            ):
                grace_ends_at = now() + HAND_BACK_GRACE
                emit_predicate(True, now(), grace_ends_at)
            auto_due = (
                phase == "human"
                and met is True
                and not flags.auto_handback_disabled
                and grace_ends_at is not None
                and now() >= grace_ends_at
            )
            if phase == "human" and (flags.handback_requested or auto_due):
                at = now()
                close_open(at)
                open_kind("verifying", at)
                emit_control("verifying", at, deadline_at)
                verdict = poll_check()
                if verdict is False:
                    at = now()
                    close_open(at)
                    store.release_holder(work.run_id, at)
                    open_kind("waiting", at)
                    emit_control("waiting", at, deadline_at)
                    phase = "waiting"
                    grace_ends_at = None
                    last_met = verdict
                    sleep(PARK_POLL_SECONDS)
                    continue
                at = now()
                close_open(at)
                store.resume(work.run_id, at)
                enter_automation(at)
                emit_control("automation", at)
                if credentials is not None and loaded is not None:
                    write_auth_states(
                        credentials, loaded, page.context, include_consented=False
                    )
                if capture is not None:
                    capture.resume("takeover")
                return "verified" if verdict is True else "handback"
            sleep(PARK_POLL_SECONDS)
        close_open(now())
        return "lost"

    def check_control(*_: object) -> None:
        if control is None:
            return
        flags = control()
        if flags.cancel_requested:
            raise RunCancelled
        if flags.pause_requested:
            raise RunPaused

    loaded: CredentialSet | None = None
    values: dict[str, Any] = dict(work.variables)
    try:
        if credentials is not None:
            loaded = credentials.fetch()
            values.update(loaded.secrets)
    except MissingSecret as error:
        terminal_status = "failed"
        failure_reason = "missing_secret"
        failure_detail = str(error)
        _skip_remaining(work, store, 0)
        loaded = None

    secret_values = (
        [value for value in loaded.secrets.values() if value]
        if loaded is not None
        else []
    )
    store = RedactingStore(store, secret_values)

    with TemporaryDirectory(prefix=f"run-{work.run_id}-", dir=profile_root) as profile:
        if failure_reason == "missing_secret":
            context = None
        else:
            try:
                context = browser_type.launch_persistent_context(
                    profile, headless=headless
                )
                context_holder.append(context)
                if loaded is not None:
                    inject(context, loaded.auth_states)
            except PlaywrightError as error:
                terminal_status = "failed"
                failure_reason = "startup_failed"
                failure_detail = str(error)
                _skip_remaining(work, store, 0)
                context = None
        if context is not None:
            capture = TraceCapture(context, profile, store, work)
            traces[0] = capture
            download_index = 0
            secret_variable_names = frozenset(
                variable.name for variable in work.document.variables if variable.secret
            )
            try:
                capture.start()
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
                    except RunPaused:
                        if (
                            park_for_human(work.takeover_timeout_ms, page, None)
                            == "lost"
                        ):
                            break
                    if elapsed() >= work.timeout_ms:
                        terminal_status = "failed"
                        failure_reason = "run_timeout"
                        failure_detail = "the Run exhausted its automation timeout"
                        _skip_remaining(work, store, position)
                        break

                    if isinstance(step, TakeoverStep) and not step.disabled:
                        timeout = step.payload.timeout_ms or work.takeover_timeout_ms
                        parked = park_for_human(
                            timeout, page, step.payload.success_check
                        )
                        if parked == "lost":
                            break
                        if parked == "verified":
                            announce_started(store, work, step, position)
                            outcome = StepOutcome(
                                step_id=step.id,
                                position=position,
                                status="passed",
                                started_at=now(),
                                ended_at=now(),
                                completed_by_human=True,
                            )
                            download_index = record_step_artifacts(
                                page,
                                store,
                                work,
                                step,
                                outcome,
                                [],
                                download_index,
                                automation=in_automation,
                            )
                            store.add_result(work.run_id, outcome)
                            announce_finished(store, work, outcome)
                            continue

                    announce_started(store, work, step, position)
                    downloads: list[DownloadCapture] = []
                    hole = any(
                        name in secret_variable_names for name in step.references()
                    )
                    if hole:
                        capture.pause("secret")
                    try:
                        try:
                            outcome = execute_step(
                                page,
                                step,
                                position,
                                work.default_step_timeout_ms,
                                values,
                                on_control=check_control,
                                on_challenge=report_challenge(store, work, step),
                                downloads=downloads,
                            )
                        except RunPaused:
                            if (
                                park_for_human(work.takeover_timeout_ms, page, None)
                                == "lost"
                            ):
                                break
                            downloads = []
                            try:
                                outcome = execute_step(
                                    page,
                                    step,
                                    position,
                                    work.default_step_timeout_ms,
                                    values,
                                    on_control=check_control,
                                    on_challenge=report_challenge(store, work, step),
                                    downloads=downloads,
                                )
                            except RunCancelled:
                                terminal_status = "cancelled"
                                _skip_remaining(work, store, position)
                                break
                        except RunCancelled:
                            terminal_status = "cancelled"
                            _skip_remaining(work, store, position)
                            break
                    finally:
                        if hole:
                            capture.resume("secret")
                    if lost.is_set():
                        break
                    download_index = record_step_artifacts(
                        page,
                        store,
                        work,
                        step,
                        outcome,
                        downloads,
                        download_index,
                        automation=in_automation,
                    )
                    store.add_result(work.run_id, outcome)
                    announce_finished(store, work, outcome)
                    if outcome.status == "failed":
                        terminal_status = "failed"
                        failure_reason = failure_reason_for(outcome)
                        failure_detail = outcome.error_message
                        _skip_remaining(work, store, position + 1)
                        break
                    try:
                        check_control()
                    except RunCancelled:
                        terminal_status = "cancelled"
                        _skip_remaining(work, store, position + 1)
                        break
                    except RunPaused:
                        if (
                            park_for_human(work.takeover_timeout_ms, page, None)
                            == "lost"
                        ):
                            break
                    if elapsed() >= work.timeout_ms:
                        terminal_status = "failed"
                        failure_reason = "run_timeout"
                        failure_detail = "the Run exhausted its automation timeout"
                        _skip_remaining(work, store, position + 1)
                        break
            finally:
                if (
                    credentials is not None
                    and loaded is not None
                    and terminal_status == "succeeded"
                ):
                    write_auth_states(
                        credentials, loaded, context, include_consented=True
                    )
                capture.finish()
                close_quietly(context)

    stop.set()
    if watcher is not None:
        watcher.join(timeout=heartbeat_every + 1)
    if lost.is_set():
        # A 409 means the row is already terminal; do not overwrite it.
        close_open(now())
        return

    ended_at = now()
    if in_automation:
        automation_ms += int((monotonic() - automation_clock) * 1000)
    close_open(ended_at)
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


def write_auth_states(
    credentials: Credentials,
    loaded: CredentialSet,
    context: Any,
    *,
    include_consented: bool,
) -> None:
    known = {
        str(state["domain"])
        for state in loaded.auth_states
        if isinstance(state, Mapping)
    }
    try:
        states, new_domains = capture(context, known)
        if include_consented:
            consented = credentials.consents()
            credentials.write_back(existing_and_consented(states, known, consented), [])
        else:
            credentials.write_back(
                existing_and_consented(states, known, []), new_domains
            )
    except Exception:
        log.exception("auth state write-back failed")


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


def failure_reason_for(outcome: StepOutcome) -> str:
    if (
        outcome.diagnostics is not None
        and outcome.diagnostics.get("kind") == "suspected_challenge"
    ):
        return "auth_challenge"
    return "step_failed"


def report_challenge(
    store: ResultStore, work: RunWork, step: Step
) -> Callable[[Mapping[str, Any]], None]:
    def emit(diagnostic: Mapping[str, Any]) -> None:
        store.emit(
            work.run_id,
            "diagnostic",
            {
                "run_id": work.run_id,
                "step_id": step.id,
                "kind": diagnostic["kind"],
                "detail": diagnostic["detail"],
                "at": now(),
            },
        )

    return emit


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
        "completed_by_human": outcome.completed_by_human,
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


def should_screenshot(
    step: Step, outcome: StepOutcome, *, automation: bool = True
) -> bool:
    # Leak prevention outranks diagnostics: a Step that fails during
    # waiting/human/verifying takes no screenshot (an MFA code may be on screen).
    if not automation:
        return False
    if outcome.status == "failed":
        return True
    return outcome.status == "passed" and step.screenshot


def record_step_artifacts(
    page: Page,
    store: ResultStore,
    work: RunWork,
    step: Step,
    outcome: StepOutcome,
    downloads: list[DownloadCapture],
    download_index: int,
    *,
    automation: bool = True,
) -> int:
    next_index = download_index
    for captured in downloads:
        store.add_artifact(
            work.run_id,
            kind="download",
            body=captured.body,
            content_type=captured.content_type,
            index=next_index,
            step_id=step.id,
            filename=captured.filename,
        )
        next_index += 1
    if should_screenshot(step, outcome, automation=automation):
        try:
            body = page.screenshot(type="png")
        except PlaywrightError:
            log.exception("screenshot failed")
        else:
            store.add_artifact(
                work.run_id,
                kind="screenshot",
                body=body,
                content_type="image/png",
                index=0,
                step_id=step.id,
                filename="screenshot.png",
            )
    return next_index


def save_trace_chunk(
    context: Any,
    profile: str,
    store: ResultStore,
    work: RunWork,
    index: int,
    *,
    final: bool = False,
) -> None:
    path = Path(profile) / f"trace-{index}.zip"
    try:
        if final:
            context.tracing.stop(path=str(path))
        else:
            context.tracing.stop_chunk(path=str(path))
    except Exception:
        log.exception("trace stop failed")
        return
    if not path.is_file():
        return
    store.add_artifact(
        work.run_id,
        kind="trace",
        body=path.read_bytes(),
        content_type="application/zip",
        index=index,
        filename=f"trace-{index}.zip",
    )


def execute_step(
    page: Page,
    step: Step,
    position: int,
    default_timeout_ms: int,
    variables: Mapping[str, Any],
    on_control: Callable[..., None] | None = None,
    on_challenge: Callable[[Mapping[str, Any]], None] | None = None,
    downloads: list[DownloadCapture] | None = None,
) -> StepOutcome:
    """Execute one Step, returning only after its observable outcome is complete."""
    started_at = now()
    if step.disabled:
        return StepOutcome(step.id, position, "skipped", None, started_at)

    timeout_ms = step.timeout_ms or default_timeout_ms
    deadline = Deadline.in_ms(timeout_ms)
    flagged: dict[str, Any] | None = None

    def capture(diagnostic: Mapping[str, Any]) -> None:
        nonlocal flagged
        flagged = dict(diagnostic)
        if on_challenge is not None:
            on_challenge(diagnostic)

    try:
        matched, extracted = perform(
            page,
            step,
            deadline,
            variables,
            watch_challenge(page, timeout_ms, on_control, capture),
            downloads=downloads,
        )
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
            diagnostics=flagged if status == "failed" else None,
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
            diagnostics=flagged,
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


def watch_challenge(
    page: Page,
    timeout_ms: int,
    on_control: Callable[..., None] | None,
    on_challenge: Callable[[Mapping[str, Any]], None] | None,
) -> Callable[..., None]:
    started = monotonic()
    flagged = False

    def on_walk(*args: object) -> None:
        nonlocal flagged
        if on_control is not None:
            on_control(*args)
        if flagged or on_challenge is None:
            return
        if (monotonic() - started) * 1000 < timeout_ms / 2:
            return
        if not page_shows_challenge(page):
            return
        flagged = True
        on_challenge(
            {
                "kind": "suspected_challenge",
                "detail": (
                    "the page shows a known challenge while this Step "
                    "is still resolving"
                ),
            }
        )

    return on_walk


def success_check_met(page: Page, target: Target) -> bool:
    """One read-only walk of the success check. Never an action."""
    try:
        found = resolve(page, target, Deadline(monotonic() - 1))
    except PlaywrightError:
        return False
    return isinstance(found, Resolved)


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
    downloads: list[DownloadCapture] | None = None,
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
        with page.expect_download(timeout=deadline.remaining_ms) as pending:
            found.locator.click(timeout=deadline.remaining_ms)
        if downloads is not None:
            downloads.append(captured_download(pending.value))
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
        return None, None
    raise AssertionError(f"unhandled Step type: {step.type}")


def interpolate(value: str, variables: Mapping[str, Any]) -> str:
    """Substitute the declared Run values in navigate and type strings."""
    return REFERENCE.sub(
        lambda reference: str(variables.get(reference.group(1), reference.group(0))),
        value,
    )


def captured_download(downloaded: Any) -> DownloadCapture:
    """Read the file Playwright saved, with the name the site suggested."""
    filename = Path(str(downloaded.suggested_filename)).name or "download"
    path = downloaded.path()
    body = Path(path).read_bytes() if path else b""
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return DownloadCapture(filename=filename, content_type=content_type, body=body)
