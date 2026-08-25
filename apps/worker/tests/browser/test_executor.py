"""The Worker executor drives fixture pages and records the Run at its seam."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from uuid import UUID, uuid4

import pytest
from step_by_step_core.document import WorkflowDocument
from step_by_step_worker.control import ControlFlags
from step_by_step_worker.dispatch import work_once
from step_by_step_worker.executor import RunWork, StepOutcome, execute
from step_by_step_worker.heartbeat import RunTerminal
from step_by_step_worker.store import work_from_claim

pytestmark = pytest.mark.browser


@dataclass
class RecordedRun:
    results: list[StepOutcome] = field(default_factory=list)
    intervals: list[tuple[str, Any, Any]] = field(default_factory=list)
    terminal: tuple[str, str | None, int] | None = None
    available: dict[UUID, RunWork] = field(default_factory=dict)
    claim_attempts: list[UUID] = field(default_factory=list)
    claimed: set[UUID] = field(default_factory=set)
    events: list[tuple[str, Mapping[str, Any]]] = field(default_factory=list)
    logs: list[tuple[str, str, UUID | None]] = field(default_factory=list)
    parks: list[tuple[Any, Any]] = field(default_factory=list)

    def claim(
        self, run_id: UUID, worker_id: str, vnc_endpoint: str, at: Any
    ) -> RunWork | None:
        self.claim_attempts.append(run_id)
        if run_id in self.claimed:
            return None
        found = self.available.get(run_id)
        if found is not None:
            self.claimed.add(run_id)
        return found

    def start_interval(self, run_id: UUID, kind: str, at: Any) -> object:
        self.intervals.append((kind, at, None))
        return len(self.intervals) - 1

    def end_interval(self, handle: object, at: Any) -> None:
        assert isinstance(handle, int)
        index = handle
        kind, started, _ = self.intervals[index]
        self.intervals[index] = (kind, started, at)

    def add_result(self, run_id: UUID, result: StepOutcome) -> None:
        self.results.append(result)

    def finish_run(
        self,
        run_id: UUID,
        status: str,
        failure_reason: str | None,
        failure_detail: str | None,
        automation_ms: int,
        at: Any,
    ) -> None:
        self.terminal = (status, failure_reason, automation_ms)

    def emit(self, run_id: UUID, event_type: str, payload: Mapping[str, Any]) -> None:
        self.events.append((event_type, payload))

    def log(
        self,
        run_id: UUID,
        level: str,
        text: str,
        step_id: UUID | None = None,
    ) -> None:
        self.logs.append((level, text, step_id))

    def park(self, run_id: UUID, deadline_at: Any, at: Any) -> None:
        self.parks.append((deadline_at, at))

    def resume(self, run_id: UUID, at: Any) -> None:
        return

    def release_holder(self, run_id: UUID, at: Any) -> None:
        return


def step(
    step_type: str, label: str, payload: dict[str, Any], **flags: Any
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "type": step_type,
        "label": label,
        "payload": payload,
        **flags,
    }


def target(*candidates: tuple[str, str]) -> dict[str, Any]:
    return {
        "candidates": [{"kind": kind, "value": value} for kind, value in candidates]
    }


def work(document: dict[str, Any], **changes: Any) -> RunWork:
    values: dict[str, Any] = {
        "run_id": uuid4(),
        "document": WorkflowDocument.model_validate(document),
        "default_step_timeout_ms": 5_000,
        "timeout_ms": 30_000,
        "variables": {},
    }
    values.update(changes)
    return RunWork(**values)


def test_three_steps_succeed_in_one_automation_interval(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "type",
                    "Enter name",
                    {"target": target(("testid", "name")), "value": "Ada"},
                ),
                step("click", "Save", {"target": target(("testid", "save"))}),
            ],
        }
    )

    execute(run, playwright_driver.chromium, recorded, tmp_path, headless=True)

    assert [result.status for result in recorded.results] == [
        "passed",
        "passed",
        "passed",
    ]
    assert [result.position for result in recorded.results] == [0, 1, 2]
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)
    assert len(recorded.intervals) == 1
    kind, started, ended = recorded.intervals[0]
    assert kind == "automation"
    assert started <= ended
    assert list(tmp_path.iterdir()) == []
    kinds = [event_type for event_type, _ in recorded.events]
    assert kinds == [
        "step.started",
        "step.finished",
        "step.started",
        "step.finished",
        "step.started",
        "step.finished",
        "run.status",
    ]
    assert recorded.events[-1][1]["status"] == "succeeded"
    assert [payload["position"] for _, payload in recorded.events[:6:2]] == [0, 1, 2]
    assert kinds.count("run.status") == 1
    assert [step_id for _, _, step_id in recorded.logs] == [
        result.step_id for result in recorded.results
    ]


def test_selector_drift_and_candidate_count_are_recorded(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "click",
                    "Save",
                    {
                        "target": target(
                            ("testid", "gone"),
                            ("text", "also gone"),
                            ("testid", "save"),
                        )
                    },
                ),
            ],
        }
    )

    execute(run, playwright_driver.chromium, recorded, tmp_path, headless=True)

    drifted = recorded.results[1]
    assert drifted.status == "passed"
    assert drifted.matched_candidate_rank == 2
    assert drifted.candidate_count == 3


def test_required_missing_target_fails_and_skips_the_rest(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "click",
                    "Missing",
                    {"target": target(("testid", "gone"))},
                    timeoutMs=5,
                ),
                step("click", "Unreached", {"target": target(("testid", "save"))}),
            ],
        }
    )

    execute(run, playwright_driver.chromium, recorded, tmp_path, headless=True)

    assert [result.status for result in recorded.results] == [
        "passed",
        "failed",
        "skipped",
    ]
    assert recorded.results[1].error_code == "no_candidate_resolved"
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("failed", "step_failed")


def test_optional_missing_target_and_disabled_step_are_skipped(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "click",
                    "Optional missing",
                    {"target": target(("testid", "gone"))},
                    optional=True,
                    timeoutMs=5,
                ),
                step(
                    "click",
                    "Disabled save",
                    {"target": target(("testid", "save"))},
                    disabled=True,
                ),
                step(
                    "extract",
                    "Read save marker",
                    {
                        "target": target(("css", "body")),
                        "outputName": "saved",
                        "mode": "scalar",
                        "attribute": "data-saved",
                    },
                ),
                step(
                    "type",
                    "Continue",
                    {"target": target(("testid", "name")), "value": "Grace"},
                ),
            ],
        }
    )

    execute(run, playwright_driver.chromium, recorded, tmp_path, headless=True)

    assert [result.status for result in recorded.results] == [
        "passed",
        "skipped",
        "skipped",
        "passed",
        "passed",
    ]
    assert recorded.results[3].extracted_value is None
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)


def test_claimed_test_run_drives_the_draft_snapshot(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    draft_step_id = uuid4()
    run = work_from_claim(
        {
            "id": uuid4(),
            "is_test": True,
            "draft_snapshot": {
                "variables": [],
                "steps": [
                    step(
                        "navigate",
                        "Draft page",
                        {"url": f"{fixture_site}/executor.html"},
                        id=str(draft_step_id),
                    )
                ],
            },
            "version_document": {
                "variables": [],
                "steps": [
                    step(
                        "navigate",
                        "Published page",
                        {"url": "http://127.0.0.1:1/not-the-draft"},
                    )
                ],
            },
            "default_step_timeout_ms": 5_000,
            "timeout_ms": 30_000,
            "variables": {},
        }
    )
    recorded = RecordedRun()

    execute(run, playwright_driver.chromium, recorded, tmp_path, headless=True)

    assert [result.step_id for result in recorded.results] == [draft_step_id]
    assert recorded.results[0].status == "passed"


class Queue:
    def __init__(self, *run_ids: UUID) -> None:
        self.run_ids = list(run_ids)

    def brpop(self, keys: str, timeout: int) -> tuple[bytes, bytes] | None:
        if not self.run_ids:
            return None
        return keys.encode(), str(self.run_ids.pop(0)).encode()


def test_dispatch_drops_unclaimable_and_duplicate_ids_and_runs_sequentially(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    cancelled_id = uuid4()
    first = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "First", {"url": f"{fixture_site}/executor.html"})
            ],
        }
    )
    second = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Second", {"url": f"{fixture_site}/executor.html"})
            ],
        }
    )
    recorded = RecordedRun(available={first.run_id: first, second.run_id: second})
    queue = Queue(cancelled_id, first.run_id, first.run_id, second.run_id)

    assert work_once(
        queue,
        recorded,
        playwright_driver.chromium,
        tmp_path,
        worker_id="worker-1",
        vnc_endpoint="worker-1:5900",
        headless=True,
    )
    assert work_once(
        queue,
        recorded,
        playwright_driver.chromium,
        tmp_path,
        worker_id="worker-1",
        vnc_endpoint="worker-1:5900",
        headless=True,
    )
    assert not work_once(
        queue,
        recorded,
        playwright_driver.chromium,
        tmp_path,
        worker_id="worker-1",
        vnc_endpoint="worker-1:5900",
        headless=True,
    )

    assert recorded.claim_attempts == [
        cancelled_id,
        first.run_id,
        first.run_id,
        second.run_id,
    ]
    assert [result.status for result in recorded.results] == ["passed", "passed"]


def test_run_timeout_is_checked_at_a_step_boundary(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "navigate",
                    "Never reached",
                    {"url": f"{fixture_site}/executor.html"},
                ),
                step("click", "Also skipped", {"target": target(("testid", "save"))}),
            ],
        },
        timeout_ms=1,
    )

    execute(run, playwright_driver.chromium, recorded, tmp_path, headless=True)

    assert [result.status for result in recorded.results] == ["skipped", "skipped"]
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("failed", "run_timeout")


def test_a_running_executor_heartbeats_every_few_seconds(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    beats: list[float] = []
    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "wait",
                    "Hold the browser",
                    {"mode": "duration", "durationMs": 200},
                )
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        heartbeat=lambda: beats.append(monotonic()),
        heartbeat_every=0.05,
    )

    assert len(beats) >= 2
    gaps = [later - earlier for earlier, later in pairwise(beats)]
    assert gaps and min(gaps) >= 0.04


def test_a_terminal_heartbeat_abandons_the_run_and_closes_the_browser(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    beats = 0

    def beat() -> None:
        nonlocal beats
        beats += 1
        raise RunTerminal

    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "wait",
                    "Hold the browser",
                    {"mode": "duration", "durationMs": 5_000},
                ),
                step(
                    "navigate",
                    "Must not run",
                    {"url": f"{fixture_site}/executor.html"},
                ),
            ],
        }
    )
    started = monotonic()

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        heartbeat=beat,
        heartbeat_every=0.05,
    )

    assert monotonic() - started < 2
    assert beats >= 1
    assert all(result.status != "passed" for result in recorded.results)
    assert list(tmp_path.iterdir()) == []


def test_cancel_during_an_in_flight_step_completes_it_and_skips_the_rest(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    polls = 0

    def flags() -> ControlFlags:
        nonlocal polls
        polls += 1
        return ControlFlags(cancel_requested=polls > 1)

    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "wait",
                    "Hold the browser",
                    {"mode": "duration", "durationMs": 50},
                ),
                step(
                    "navigate",
                    "Must not run",
                    {"url": f"{fixture_site}/executor.html"},
                ),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=flags,
    )

    assert [result.status for result in recorded.results] == ["passed", "skipped"]
    assert recorded.results[0].started_at is not None
    assert recorded.results[0].ended_at is not None
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("cancelled", None)


def test_cancel_during_resolve_skips_before_the_action(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()

    def flags() -> ControlFlags:
        started_click = any(
            event_type == "step.started" and payload.get("position") == 1
            for event_type, payload in recorded.events
        )
        return ControlFlags(cancel_requested=started_click)

    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "navigate",
                    "Open form",
                    {"url": f"{fixture_site}/executor.html"},
                ),
                step(
                    "click",
                    "Missing",
                    {"target": target(("testid", "gone"))},
                    timeoutMs=5_000,
                ),
                step(
                    "click",
                    "Must not run",
                    {"target": target(("testid", "save"))},
                ),
            ],
        }
    )
    begun = monotonic()

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=flags,
    )

    assert monotonic() - begun < 2
    assert [result.status for result in recorded.results] == [
        "passed",
        "skipped",
        "skipped",
    ]
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("cancelled", None)


def open_kinds(recorded: RecordedRun) -> set[str]:
    return {kind for kind, _, ended in recorded.intervals if ended is None}


def kinds_in_order(recorded: RecordedRun) -> list[str]:
    return [kind for kind, _, _ in recorded.intervals]


def take_control_then_hand_back(recorded: RecordedRun) -> Callable[[], ControlFlags]:
    def flags() -> ControlFlags:
        opened = open_kinds(recorded)
        if "human" in opened:
            return ControlFlags(holder_present=True, handback_requested=True)
        if "waiting" in opened:
            return ControlFlags(holder_present=True)
        return ControlFlags()

    return flags


def test_pause_for_takeover_parks_before_acting(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step("pause-for-takeover", "Need a person", {"message": "Solve this"}),
                step("click", "Save", {"target": target(("testid", "save"))}),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=take_control_then_hand_back(recorded),
    )

    assert [result.status for result in recorded.results] == [
        "passed",
        "passed",
        "passed",
    ]
    assert kinds_in_order(recorded)[:4] == [
        "automation",
        "waiting",
        "human",
        "verifying",
    ]
    assert kinds_in_order(recorded)[-1] == "automation"
    assert recorded.parks
    parked_at, started = recorded.parks[0]
    assert parked_at - started == timedelta(milliseconds=1_800_000)
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)
    assert "predicate" not in [event_type for event_type, _ in recorded.events]
    assert recorded.results[1].completed_by_human is False


def test_pause_for_takeover_override_changes_the_deadline(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "pause-for-takeover",
                    "Short wait",
                    {"timeoutMs": 5_000},
                )
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=take_control_then_hand_back(recorded),
    )

    assert recorded.parks
    parked_at, started = recorded.parks[0]
    assert parked_at - started == timedelta(milliseconds=5_000)


def test_pause_during_resolve_retries_the_step_after_handback(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    asked = {"pause": False}

    def flags() -> ControlFlags:
        opened = open_kinds(recorded)
        click_started = any(
            event_type == "step.started" and payload.get("position") == 1
            for event_type, payload in recorded.events
        )
        if "human" in opened:
            return ControlFlags(holder_present=True, handback_requested=True)
        if "waiting" in opened:
            asked["pause"] = True
            return ControlFlags(holder_present=True)
        if click_started and not asked["pause"]:
            return ControlFlags(pause_requested=True)
        return ControlFlags()

    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step("click", "Save", {"target": target(("testid", "save"))}),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=flags,
    )

    assert [result.status for result in recorded.results] == ["passed", "passed"]
    click = recorded.results[1]
    waiting = next(
        started for kind, started, _ in recorded.intervals if kind == "waiting"
    )
    announced = next(
        payload["at"]
        for event_type, payload in recorded.events
        if event_type == "step.started" and payload.get("position") == 1
    )
    assert announced <= waiting <= click.ended_at
    assert "verifying" in kinds_in_order(recorded)
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)


def test_waiting_time_is_excluded_from_automation_ms(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    waited = {"done": False}

    def flags() -> ControlFlags:
        opened = open_kinds(recorded)
        if "waiting" in opened and not waited["done"]:
            sleep(0.3)
            waited["done"] = True
        if "human" in opened:
            return ControlFlags(holder_present=True, handback_requested=True)
        if "waiting" in opened:
            return ControlFlags(holder_present=True)
        return ControlFlags()

    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "wait",
                    "A little work",
                    {"mode": "duration", "durationMs": 50},
                ),
                step("pause-for-takeover", "Need a person", {}),
            ],
        }
    )
    begun = monotonic()

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=flags,
    )
    wall_ms = int((monotonic() - begun) * 1000)

    assert recorded.terminal is not None
    automation_ms = recorded.terminal[2]
    assert automation_ms < 250
    assert wall_ms >= 300
    assert automation_ms < wall_ms - 200
    assert {kind for kind, _, _ in recorded.intervals} >= {
        "automation",
        "waiting",
        "human",
        "verifying",
    }


def success_check(*candidates: tuple[str, str]) -> dict[str, Any]:
    return {"successCheck": target(*candidates)}


def predicate_events(recorded: RecordedRun) -> list[Mapping[str, Any]]:
    return [
        payload for event_type, payload in recorded.events if event_type == "predicate"
    ]


def test_waiting_on_a_success_check_streams_predicate_events(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()

    def flags() -> ControlFlags:
        mets = [payload["met"] for payload in predicate_events(recorded)]
        opened = open_kinds(recorded)
        if True in mets:
            if "human" in opened:
                return ControlFlags(holder_present=True, handback_requested=True)
            if "waiting" in opened:
                return ControlFlags(holder_present=True)
        return ControlFlags()

    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "navigate",
                    "Open late page",
                    {"url": f"{fixture_site}/late-button.html"},
                ),
                step(
                    "pause-for-takeover",
                    "Wait for the button",
                    success_check(("css", "#save-invoice")),
                ),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=flags,
    )

    mets = [payload["met"] for payload in predicate_events(recorded)]
    assert False in mets
    assert True in mets
    first_met = next(
        payload for payload in predicate_events(recorded) if payload["met"] is True
    )
    assert "grace_ends_at" not in first_met
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)


def test_a_met_check_during_control_hands_back_after_the_grace(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()

    def flags() -> ControlFlags:
        opened = open_kinds(recorded)
        if "human" in opened or "waiting" in opened:
            return ControlFlags(holder_present=True)
        return ControlFlags()

    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "pause-for-takeover",
                    "Need a person",
                    success_check(("testid", "save")),
                ),
                step("click", "Save", {"target": target(("testid", "save"))}),
            ],
        }
    )
    begun = monotonic()

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=flags,
    )
    elapsed = monotonic() - begun

    grace = next(
        payload
        for payload in predicate_events(recorded)
        if payload.get("grace_ends_at") is not None
    )
    assert grace["met"] is True
    assert elapsed >= 5.5
    assert elapsed < 12
    assert [result.status for result in recorded.results] == [
        "passed",
        "passed",
        "passed",
    ]
    assert recorded.results[1].completed_by_human is True
    assert kinds_in_order(recorded)[:5] == [
        "automation",
        "waiting",
        "human",
        "verifying",
        "automation",
    ]
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)


def test_hold_keeps_control_after_the_check_is_met(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    handed = {"now": False}

    def flags() -> ControlFlags:
        opened = open_kinds(recorded)
        grace = next(
            (
                payload.get("grace_ends_at")
                for payload in predicate_events(recorded)
                if payload.get("grace_ends_at") is not None
            ),
            None,
        )
        if "human" in opened and grace is not None:
            human = next(
                (started, ended)
                for kind, started, ended in recorded.intervals
                if kind == "human"
            )
            held_for = (human[1] or datetime.now(UTC)) - human[0]
            if held_for.total_seconds() >= 7:
                handed["now"] = True
                return ControlFlags(
                    holder_present=True,
                    auto_handback_disabled=True,
                    handback_requested=True,
                )
            return ControlFlags(holder_present=True, auto_handback_disabled=True)
        if "human" in opened or "waiting" in opened:
            return ControlFlags(holder_present=True)
        return ControlFlags()

    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "pause-for-takeover",
                    "Need a person",
                    success_check(("testid", "save")),
                ),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=flags,
    )

    assert handed["now"] is True
    human = next(
        (started, ended)
        for kind, started, ended in recorded.intervals
        if kind == "human"
    )
    assert human[1] is not None
    assert (human[1] - human[0]).total_seconds() >= 6.5
    assert kinds_in_order(recorded).count("verifying") == 1
    assert recorded.results[-1].completed_by_human is True
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)


def test_handback_with_the_check_met_completes_the_pause_step(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "pause-for-takeover",
                    "Need a person",
                    success_check(("testid", "save")),
                ),
                step("click", "Save", {"target": target(("testid", "save"))}),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=take_control_then_hand_back(recorded),
    )

    assert [result.status for result in recorded.results] == [
        "passed",
        "passed",
        "passed",
    ]
    pause = recorded.results[1]
    assert pause.completed_by_human is True
    finished = next(
        payload
        for event_type, payload in recorded.events
        if event_type == "step.finished" and payload.get("step_id") == pause.step_id
    )
    assert finished["completed_by_human"] is True
    assert "verifying" in kinds_in_order(recorded)
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)


def test_unmet_handback_returns_to_waiting_on_the_same_deadline(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()

    def flags() -> ControlFlags:
        opened = open_kinds(recorded)
        humans = kinds_in_order(recorded).count("human")
        if "human" in opened:
            if humans <= 1:
                return ControlFlags(holder_present=True, handback_requested=True)
            return ControlFlags(holder_present=True)
        if "waiting" in opened:
            return ControlFlags(holder_present=True)
        return ControlFlags()

    def heartbeat() -> None:
        if kinds_in_order(recorded).count("human") >= 2:
            raise RunTerminal

    run = work(
        {
            "variables": [],
            "steps": [
                step("navigate", "Open form", {"url": f"{fixture_site}/executor.html"}),
                step(
                    "pause-for-takeover",
                    "Need a person",
                    success_check(("testid", "never-appears")),
                ),
                step("click", "Save", {"target": target(("testid", "save"))}),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        heartbeat=heartbeat,
        heartbeat_every=0.05,
        control=flags,
    )

    assert [result.status for result in recorded.results] == ["passed"]
    assert kinds_in_order(recorded)[:5] == [
        "automation",
        "waiting",
        "human",
        "verifying",
        "waiting",
    ]
    assert kinds_in_order(recorded).count("human") >= 2
    assert len(recorded.parks) == 1
    assert recorded.terminal is None
