"""The live Run wire: Redis events, SSE fan-out, and persisted log lines."""

import json
import os
import threading
import time
from collections.abc import Iterable, Iterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from conftest import DEV_MASTER_KEY, Account, join
from step_by_step_api import clock
from step_by_step_api.main import app
from step_by_step_api.runs.models import StepResult, StepResultStatus
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from step_by_step_core.events import events_channel, publish, publish_log
from test_runs import NewAccount, published_workflow, start

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_origin() -> Iterator[str]:
    """A real HTTP server: TestClient buffers the body and cannot observe SSE."""
    os.environ.setdefault("STEPBYSTEP_MASTER_KEY", DEV_MASTER_KEY)
    os.environ.setdefault("MAILER", "console")
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("live server did not start")
        time.sleep(0.01)
    host, port = server.servers[0].sockets[0].getsockname()[:2]
    yield f"http://{host}:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def http_client(account: Account, origin: str) -> httpx.Client:
    token = account.client.cookies.get("session")
    assert token is not None
    return httpx.Client(
        base_url=origin,
        cookies={"session": token},
        headers={"X-Organization": account.org_id},
        timeout=5.0,
    )


def logs(account: Account, run_id: str, **params: object):
    return account.client.get(f"/api/runs/{run_id}/logs", params=params)


def subscriber_count(channel: str) -> int:
    _name, count = get_redis().pubsub_numsub(channel)[0]
    return int(count)


def parse_sse(
    lines: Iterable[str], count: int, timeout: float = 3.0
) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type = ""
    data: list[str] = []
    deadline = time.monotonic() + timeout
    for line in lines:
        if time.monotonic() > deadline:
            break
        if line == "":
            if event_type:
                events.append((event_type, json.loads("\n".join(data) or "{}")))
                if len(events) >= count:
                    return events
            event_type = ""
            data = []
        elif line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data.append(line.removeprefix("data:").lstrip())
    return events


def test_a_log_line_is_a_row_and_an_sse_event(
    new_account: NewAccount, live_origin: str
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    step_id = uuid4()

    with (
        http_client(account, live_origin) as client,
        client.stream("GET", f"/api/runs/{run_id}/events") as stream,
    ):
        assert stream.status_code == 200
        seq = publish_log(
            UUID(run_id), level="info", text="clicked Save", step_id=step_id
        )
        event_type, payload = parse_sse(stream.iter_lines(), 1)[0]

    stored = logs(account, run_id)
    assert stored.status_code == 200, stored.text
    line = stored.json()[0]
    assert seq == 1
    assert event_type == "log"
    assert payload["seq"] == line["seq"] == 1
    assert payload["text"] == line["text"] == "clicked Save"
    assert payload["level"] == line["level"] == "info"
    assert payload["step_id"] == line["step_id"] == str(step_id)
    assert payload["run_id"] == run_id


def test_the_log_cap_keeps_ten_thousand_lines_and_one_truncation(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    run = UUID(run_id)

    for index in range(10_001):
        publish_log(run, level="info", text=f"line {index}")
    assert publish_log(run, level="info", text="too late") is None

    stored = logs(account, run_id).json()
    assert len(stored) == 10_001
    assert stored[0]["text"] == "line 0"
    assert stored[9_999]["text"] == "line 9999"
    assert stored[-1]["text"] == "log truncated"


def test_logs_filter_by_after_seq_and_step_id(new_account: NewAccount) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    run = UUID(run_id)
    first = uuid4()
    second = uuid4()
    publish_log(run, level="info", text="a1", step_id=first)
    publish_log(run, level="info", text="b1", step_id=second)
    publish_log(run, level="info", text="a2", step_id=first)

    later = logs(account, run_id, after_seq=1)
    only_first = logs(account, run_id, step_id=str(first))

    assert [line["text"] for line in later.json()] == ["b1", "a2"]
    assert [line["text"] for line in only_first.json()] == ["a1", "a2"]


def test_sse_hides_another_organizations_run_before_subscribing(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()
    run_id = start(owner, published_workflow(owner), variables={}).json()["run_id"]
    channel = events_channel(UUID(run_id))
    before = subscriber_count(channel)

    refused = stranger.client.get(f"/api/runs/{run_id}/events")

    assert refused.status_code == 404
    assert refused.json()["code"] == "run_not_found"
    assert subscriber_count(channel) == before
    assert logs(stranger, run_id).status_code == 404


def test_any_member_of_the_run_organization_may_subscribe(
    new_account: NewAccount, live_origin: str
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    run_id = start(owner, published_workflow(owner), variables={}).json()["run_id"]

    with (
        http_client(member, live_origin) as client,
        client.stream("GET", f"/api/runs/{run_id}/events") as stream,
    ):
        assert stream.status_code == 200
        publish(
            UUID(run_id),
            "control",
            {"run_id": run_id, "phase": "automation", "at": clock.now()},
        )
        event_type, payload = parse_sse(stream.iter_lines(), 1)[0]

    assert event_type == "control"
    assert payload["phase"] == "automation"


def test_reconnect_replays_nothing_and_detail_has_what_was_missed(
    new_account: NewAccount, live_origin: str
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    run = UUID(run_id)
    step_id = uuid4()
    started = {
        "run_id": run_id,
        "step_id": step_id,
        "position": 0,
        "at": clock.now(),
    }

    with (
        http_client(account, live_origin) as client,
        client.stream("GET", f"/api/runs/{run_id}/events") as first,
    ):
        publish(run, "step.started", started)
        assert parse_sse(first.iter_lines(), 1)[0][0] == "step.started"

    with session_scope() as db:
        db.add(
            StepResult(
                run_id=run,
                step_id=step_id,
                position=0,
                status=StepResultStatus.PASSED,
            )
        )
        db.commit()
    finished = {
        "run_id": run_id,
        "step_id": step_id,
        "status": "passed",
        "matched_candidate_rank": 0,
        "candidate_count": 1,
        "completed_by_human": False,
        "at": clock.now(),
    }

    with (
        http_client(account, live_origin) as client,
        client.stream("GET", f"/api/runs/{run_id}/events") as second,
    ):
        publish(run, "step.finished", finished)
        events = parse_sse(second.iter_lines(), 1)

    assert [event_type for event_type, _ in events] == ["step.finished"]
    detail = account.client.get(f"/api/runs/{run_id}").json()
    assert [result["step_id"] for result in detail["step_results"]] == [str(step_id)]


def test_an_artifact_event_carries_ids_only(
    new_account: NewAccount, live_origin: str
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    artifact_id = uuid4()
    step_id = uuid4()

    with (
        http_client(account, live_origin) as client,
        client.stream("GET", f"/api/runs/{run_id}/events") as stream,
    ):
        publish(
            UUID(run_id),
            "artifact",
            {
                "run_id": run_id,
                "step_id": step_id,
                "artifact_id": artifact_id,
                "kind": "screenshot",
                "at": clock.now(),
                "bytes": b"not-on-the-wire",
            },
        )
        event_type, payload = parse_sse(stream.iter_lines(), 1)[0]

    assert event_type == "artifact"
    assert set(payload) == {"run_id", "step_id", "artifact_id", "kind", "at"}
    assert payload["artifact_id"] == str(artifact_id)
    assert payload["kind"] == "screenshot"
    assert all(not isinstance(value, (bytes, bytearray)) for value in payload.values())


def test_watching_published_step_events_delivers_each_exactly_once(
    new_account: NewAccount, live_origin: str
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    run = UUID(run_id)
    steps = [uuid4() for _ in range(3)]

    with (
        http_client(account, live_origin) as client,
        client.stream("GET", f"/api/runs/{run_id}/events") as stream,
    ):
        at = clock.now()
        for position, step_id in enumerate(steps):
            publish(
                run,
                "step.started",
                {"run_id": run_id, "step_id": step_id, "position": position, "at": at},
            )
            publish(
                run,
                "step.finished",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "status": "passed",
                    "matched_candidate_rank": 0,
                    "candidate_count": 1,
                    "completed_by_human": False,
                    "at": at,
                },
            )
        publish(
            run,
            "run.status",
            {"run_id": run_id, "status": "succeeded", "at": at},
        )
        events = parse_sse(stream.iter_lines(), 7)

    kinds = [event_type for event_type, _ in events]
    assert kinds == [
        "step.started",
        "step.finished",
        "step.started",
        "step.finished",
        "step.started",
        "step.finished",
        "run.status",
    ]
    assert [payload["step_id"] for _, payload in events[:6:2]] == [
        str(step_id) for step_id in steps
    ]
    assert events[-1][1]["status"] == "succeeded"
    assert kinds.count("run.status") == 1
