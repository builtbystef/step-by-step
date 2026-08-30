import json
from collections.abc import Mapping
from datetime import datetime
from io import BytesIO
from pathlib import Path
from time import sleep
from typing import Any
from uuid import UUID
from zipfile import ZipFile

import pytest
from step_by_step_core.document import TypeStep
from step_by_step_worker.control import ControlFlags
from step_by_step_worker.executor import execute
from test_executor import (
    RecordedArtifact,
    RecordedRun,
    kinds_in_order,
    open_kinds,
    screenshots_of,
    step,
    target,
    work,
)
from test_injection import RecordedCredentials

pytestmark = pytest.mark.browser

SECRET = "s3cret-zx9q2m"


def traces_of(recorded: RecordedRun) -> list[RecordedArtifact]:
    return [artifact for artifact in recorded.artifacts if artifact.kind == "trace"]


def trace_actions(body: bytes) -> list[str]:
    actions: list[str] = []
    with ZipFile(BytesIO(body)) as archive:
        for name in archive.namelist():
            if not name.endswith(".trace"):
                continue
            for line in archive.read(name).decode().splitlines():
                event = json.loads(line)
                if event.get("type") == "before" and event.get("method"):
                    actions.append(str(event["method"]))
    return actions


def trace_wall_times_ms(body: bytes) -> list[float]:
    times: list[float] = []
    with ZipFile(BytesIO(body)) as archive:
        for name in archive.namelist():
            if not name.endswith(".trace"):
                continue
            for line in archive.read(name).decode().splitlines():
                event = json.loads(line)
                if "wallTime" in event:
                    times.append(float(event["wallTime"]))
                snapshot = event.get("snapshot")
                if isinstance(snapshot, Mapping) and "wallTime" in snapshot:
                    times.append(float(snapshot["wallTime"]))
    return times


def blob_holds(body: bytes, secret: str) -> bool:
    needle = secret.encode()
    if needle in body:
        return True
    try:
        archive = ZipFile(BytesIO(body))
    except Exception:
        return False
    with archive:
        return any(needle in archive.read(info.filename) for info in archive.infolist())


def secret_workflow(origin: str) -> dict[str, Any]:
    return {
        "variables": [{"name": "password", "secret": True}],
        "steps": [
            step("navigate", "Open form", {"url": f"{origin}/executor.html"}),
            step(
                "type",
                "Type the password",
                {
                    "target": target(("testid", "password")),
                    "value": "{{password}}",
                },
            ),
            step("click", "Save", {"target": target(("testid", "save"))}),
        ],
    }


def test_trace_has_a_hole_around_a_secret_typing_step(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    credentials = RecordedCredentials(secrets={"password": SECRET})
    run = work(secret_workflow(fixture_site))

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        credentials=credentials,
    )

    chunks = traces_of(recorded)
    assert recorded.terminal is not None
    assert recorded.terminal[0] == "succeeded"
    assert len(chunks) >= 2
    assert [artifact.index for artifact in chunks] == list(range(len(chunks)))
    actions = [trace_actions(chunk.body) for chunk in chunks]
    assert "fill" not in [action for chunk in actions for action in chunk]
    assert any("goto" in chunk for chunk in actions)
    assert any("click" in chunk for chunk in actions)
    goto_at = next(i for i, chunk in enumerate(actions) if "goto" in chunk)
    click_at = next(i for i, chunk in enumerate(actions) if "click" in chunk)
    assert goto_at < click_at


def test_takeover_pauses_tracing_and_screenshots_then_resumes(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    human_shots: list[int] = []
    human_traces: list[int] = []
    page_alive = {"ok": False}

    def flags() -> ControlFlags:
        opened = open_kinds(recorded)
        if "human" in opened:
            human_shots.append(len(screenshots_of(recorded)))
            human_traces.append(len(traces_of(recorded)))
            sleep(0.2)
            human_shots.append(len(screenshots_of(recorded)))
            human_traces.append(len(traces_of(recorded)))
            page_alive["ok"] = True
            return ControlFlags(
                holder_present=True,
                handback_requested=True,
                auto_handback_disabled=True,
            )
        if "waiting" in opened:
            return ControlFlags(holder_present=True)
        return ControlFlags()

    click = step(
        "click",
        "Save",
        {"target": target(("testid", "save"))},
        screenshot=True,
    )
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
                    "pause-for-takeover",
                    "Need a person",
                    {"successCheck": target(("testid", "save"))},
                ),
                click,
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

    assert recorded.terminal is not None
    assert recorded.terminal[0] == "succeeded"
    assert page_alive["ok"]
    assert human_shots[0] == human_shots[1]
    assert human_traces[0] == human_traces[1]
    assert "waiting" in kinds_in_order(recorded)
    assert "human" in kinds_in_order(recorded)
    assert "verifying" in kinds_in_order(recorded)
    chunks = traces_of(recorded)
    assert len(chunks) >= 2
    human = next(
        (started, ended)
        for kind, started, ended in recorded.intervals
        if kind == "human"
    )
    started, ended = human
    assert isinstance(started, datetime) and isinstance(ended, datetime)
    start_ms = started.timestamp() * 1000
    end_ms = ended.timestamp() * 1000
    during = [
        time
        for chunk in chunks
        for time in trace_wall_times_ms(chunk.body)
        if start_ms <= time <= end_ms
    ]
    assert during == []
    shots = screenshots_of(recorded)
    assert any(shot.step_id == UUID(click["id"]) for shot in shots)
    actions = [trace_actions(chunk.body) for chunk in chunks]
    assert any("goto" in chunk for chunk in actions)
    assert any("click" in chunk for chunk in actions)


def test_a_run_never_stores_the_secret_value(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    credentials = RecordedCredentials(secrets={"password": SECRET})
    run = work(secret_workflow(fixture_site))

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        credentials=credentials,
    )

    assert recorded.terminal is not None
    assert recorded.terminal[0] == "succeeded"
    typed = run.document.steps[1]
    assert isinstance(typed, TypeStep)
    assert typed.payload.value == "{{password}}"
    assert SECRET not in typed.payload.value
    blobs: list[str] = []
    for result in recorded.results:
        blobs.append(result.error_message or "")
        blobs.append(str(result.diagnostics) if result.diagnostics else "")
    for _level, text, _step_id in recorded.logs:
        blobs.append(text)
    for _kind, payload in recorded.events:
        blobs.append(json.dumps(payload, default=str))
    assert SECRET not in "".join(blobs)
    for artifact in recorded.artifacts:
        assert not blob_holds(artifact.body, SECRET), artifact.kind
