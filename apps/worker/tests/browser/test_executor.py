"""The Worker executor drives fixture pages and records the Run at its seam."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from step_by_step_core.document import WorkflowDocument
from step_by_step_worker.dispatch import work_once
from step_by_step_worker.executor import RunWork, StepOutcome, execute
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
