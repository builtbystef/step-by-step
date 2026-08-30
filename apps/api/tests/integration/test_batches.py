import csv
import io
import json
import os
import threading
import time
from collections.abc import Iterable, Iterator
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from conftest import DEV_MASTER_KEY, Account, join
from sqlalchemy import select
from step_by_step_api import clock
from step_by_step_api.batches.advance import on_terminal_run
from step_by_step_api.loop import tick
from step_by_step_api.main import app
from step_by_step_api.runs.models import (
    NON_TERMINAL,
    FailureReason,
    Run,
    RunStatus,
    StepResult,
    StepResultStatus,
)
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from test_runs import published_workflow
from test_secrets import create as create_secret
from test_workflow_versions import publish
from test_workflows import NewAccount, a_navigate_step, a_target, a_workflow, save_draft

pytestmark = pytest.mark.integration
DISPATCH_LIST = "runs:dispatch"


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


@pytest.fixture(scope="module")
def live_origin() -> Iterator[str]:
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


def create_batch(account: Account, workflow_id: str, **body: object):
    return account.client.post(f"/api/workflows/{workflow_id}/batches", json=body)


def get_batch(account: Account, batch_id: str):
    return account.client.get(f"/api/batches/{batch_id}")


def list_batches(account: Account, **params: object):
    return account.client.get("/api/batches", params=params)


def batch_output(account: Account, batch_id: str, **params: object):
    return account.client.get(f"/api/batches/{batch_id}/output", params=params)


def five_rows() -> list[dict[str, object]]:
    return [{"variables": {"name": f"r{index}"}} for index in range(5)]


def workflow_with_name(account: Account) -> str:
    workflow_id = a_workflow(account)
    saved = save_draft(
        account,
        workflow_id,
        steps=[a_navigate_step(str(uuid4()))],
        variables=[{"name": "name"}],
    )
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201
    return workflow_id


def workflow_with_extract(account: Account) -> tuple[str, str]:
    workflow_id = a_workflow(account)
    extract_id = str(uuid4())
    saved = save_draft(
        account,
        workflow_id,
        steps=[
            a_navigate_step(str(uuid4())),
            {
                "id": extract_id,
                "type": "extract",
                "label": "Read the total",
                "payload": {
                    "target": a_target(),
                    "outputName": "total",
                    "mode": "scalar",
                },
            },
        ],
        variables=[{"name": "name"}, {"name": "city"}],
    )
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201
    return workflow_id, extract_id


def current_run_id(account: Account, batch_id: str) -> str:
    body = get_batch(account, batch_id).json()
    live = [row for row in body["rows"] if row["status"] == "running"]
    assert len(live) == 1, body
    run_id = live[0]["latest_run_id"]
    assert run_id is not None
    return str(run_id)


def finish_run(
    run_id: str,
    status: str = "succeeded",
    *,
    duration_s: int = 10,
    failure_reason: str | None = None,
) -> None:
    ended = clock.now()
    started = ended - timedelta(seconds=duration_s)
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = RunStatus(status)
        run.started_at = started
        run.ended_at = ended
        run.failure_reason = (
            FailureReason(failure_reason) if failure_reason is not None else None
        )
        db.commit()


def park_run(run_id: str) -> None:
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.started_at = clock.now()
        run.takeover_deadline_at = clock.now() + timedelta(minutes=30)
        db.commit()


def add_extract(run_id: str, step_id: str, value: object) -> None:
    with session_scope() as db:
        db.add(
            StepResult(
                run_id=UUID(run_id),
                step_id=UUID(step_id),
                position=1,
                status=StepResultStatus.PASSED,
                extracted_value=value,
            )
        )
        db.commit()


def non_terminal_of(workflow_id: str) -> list[Run]:
    with session_scope() as db:
        return list(
            db.execute(
                select(Run).where(
                    Run.workflow_id == UUID(workflow_id),
                    Run.status.in_(NON_TERMINAL),
                )
            ).scalars()
        )


def test_a_five_row_batch_advances_one_run_at_a_time(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)

    created = create_batch(account, workflow_id, name="Invoices", rows=five_rows())
    assert created.status_code == 201, created.text
    batch_id = created.json()["batch_id"]

    seen: list[str] = []
    for _ in range(5):
        live = non_terminal_of(workflow_id)
        assert len(live) == 1
        assert live[0].trigger.value == "batch"
        seen.append(str(live[0].id))
        finish_run(str(live[0].id))
        on_terminal_run(live[0].id)

    assert len(set(seen)) == 5
    assert non_terminal_of(workflow_id) == []
    body = get_batch(account, batch_id).json()
    assert [row["status"] for row in body["rows"]] == ["succeeded"] * 5
    assert all(row["latest_run_id"] in seen for row in body["rows"])


def test_advance_follows_the_terminal_event_and_the_tick_is_the_backstop(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    event_batch = create_batch(
        account, workflow_id, name="Event", rows=five_rows()[:2]
    ).json()["batch_id"]
    silenced_batch = create_batch(
        account, workflow_id, name="Silenced", rows=five_rows()[:2]
    ).json()["batch_id"]

    event_run = current_run_id(account, event_batch)
    finish_run(event_run)
    on_terminal_run(UUID(event_run))
    event_body = get_batch(account, event_batch).json()
    assert event_body["rows"][0]["status"] == "succeeded"
    assert event_body["rows"][1]["status"] == "running"
    assert event_body["rows"][1]["latest_run_id"] != event_run

    silenced_run = current_run_id(account, silenced_batch)
    finish_run(silenced_run)
    still = get_batch(account, silenced_batch).json()
    assert still["rows"][1]["status"] == "queued"
    assert still["rows"][1]["latest_run_id"] is None
    tick()
    backed = get_batch(account, silenced_batch).json()
    assert backed["rows"][0]["status"] == "succeeded"
    assert backed["rows"][1]["status"] == "running"
    assert backed["rows"][1]["latest_run_id"] is not None


def test_a_failed_row_does_not_strand_the_batch(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    batch_id = create_batch(
        account, workflow_id, name="Partial", rows=five_rows()
    ).json()["batch_id"]

    finish_run(current_run_id(account, batch_id))
    on_terminal_run(UUID(current_run_id(account, batch_id)))
    first = get_batch(account, batch_id).json()
    assert first["rows"][0]["status"] == "succeeded"
    failed_id = first["rows"][1]["latest_run_id"]
    finish_run(failed_id, "failed", failure_reason="step_failed")
    on_terminal_run(UUID(failed_id))
    for _ in range(3):
        live_id = current_run_id(account, batch_id)
        finish_run(live_id)
        on_terminal_run(UUID(live_id))

    body = get_batch(account, batch_id).json()
    assert [row["status"] for row in body["rows"]] == [
        "succeeded",
        "failed",
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert body["stats"]["failed"] == 1
    assert body["stats"]["succeeded"] == 4


def test_rerun_attaches_a_new_attempt_to_the_same_row(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    batch_id = create_batch(
        account, workflow_id, name="Retry", rows=five_rows()
    ).json()["batch_id"]
    finish_run(current_run_id(account, batch_id))
    on_terminal_run(UUID(current_run_id(account, batch_id)))
    failed_id = get_batch(account, batch_id).json()["rows"][1]["latest_run_id"]
    finish_run(failed_id, "failed", failure_reason="step_failed")
    on_terminal_run(UUID(failed_id))
    for _ in range(3):
        live_id = current_run_id(account, batch_id)
        finish_run(live_id)
        on_terminal_run(UUID(live_id))

    rerun = account.client.post(f"/api/batches/{batch_id}/rows/1/rerun")
    assert rerun.status_code == 201, rerun.text
    new_run_id = rerun.json()["run_id"]
    assert new_run_id != failed_id

    body = get_batch(account, batch_id).json()
    row = body["rows"][1]
    assert row["status"] == "running"
    assert row["latest_run_id"] == new_run_id
    assert [attempt["id"] for attempt in row["runs"]] == [failed_id, new_run_id]
    assert row["runs"][0]["status"] == "failed"
    assert [body["rows"][i]["status"] for i in (0, 2, 3, 4)] == ["succeeded"] * 4


def test_skip_cancels_a_waiting_row_and_advances(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    batch_id = create_batch(
        account, workflow_id, name="Skip", rows=five_rows()[:3]
    ).json()["batch_id"]
    waiting_id = current_run_id(account, batch_id)
    park_run(waiting_id)

    skipped = account.client.post(f"/api/batches/{batch_id}/rows/0/skip")
    assert skipped.status_code == 202, skipped.text

    body = get_batch(account, batch_id).json()
    assert body["rows"][0]["status"] == "skipped"
    assert account.client.get(f"/api/runs/{waiting_id}").json()["run"]["status"] == (
        "cancelled"
    )
    assert body["rows"][1]["status"] == "running"
    assert body["rows"][1]["latest_run_id"] is not None
    assert body["rows"][1]["latest_run_id"] != waiting_id


def test_cancel_mid_third_row_cancels_the_rest(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    batch_id = create_batch(account, workflow_id, name="Stop", rows=five_rows()).json()[
        "batch_id"
    ]
    for _ in range(2):
        live_id = current_run_id(account, batch_id)
        finish_run(live_id)
        on_terminal_run(UUID(live_id))
    third_id = current_run_id(account, batch_id)

    cancelled = account.client.post(f"/api/batches/{batch_id}/cancel")
    assert cancelled.status_code == 202, cancelled.text

    body = get_batch(account, batch_id).json()
    assert [row["status"] for row in body["rows"]] == [
        "succeeded",
        "succeeded",
        "cancelled",
        "cancelled",
        "cancelled",
    ]
    assert account.client.get(f"/api/runs/{third_id}").json()["run"]["status"] == (
        "cancelled"
    )
    assert body["stats"]["succeeded"] == 2
    assert body["stats"]["cancelled"] == 3
    assert body["stats"]["queued"] == 0
    assert body["batch"]["cancelled_at"] is not None


def test_eta_is_blank_until_three_rows_then_median_times_remaining(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    batch_id = create_batch(account, workflow_id, name="Eta", rows=five_rows()).json()[
        "batch_id"
    ]
    durations = [10, 30, 20]
    for duration in durations:
        live_id = current_run_id(account, batch_id)
        finish_run(live_id, duration_s=duration)
        on_terminal_run(UUID(live_id))
        body = get_batch(account, batch_id).json()
        if duration != 20:
            assert body.get("eta_seconds") is None
        else:
            assert body["eta_seconds"] == 40


def test_batch_output_is_one_table_in_both_formats(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id, extract_id = workflow_with_extract(account)
    rows = [
        {"variables": {"name": "Ada", "city": "London"}},
        {"variables": {"name": "Ben", "city": "Paris"}},
        {"variables": {"name": "Cyd", "city": "Rome"}},
        {"variables": {"name": "Dee", "city": "Oslo"}},
        {"variables": {"name": "Eve", "city": "Bern"}},
    ]
    batch_id = create_batch(account, workflow_id, name="Out", rows=rows).json()[
        "batch_id"
    ]
    totals = ["1", "2", "3", "4", "5"]
    for total in totals:
        live_id = current_run_id(account, batch_id)
        add_extract(live_id, extract_id, total)
        finish_run(live_id)
        on_terminal_run(UUID(live_id))

    as_json = batch_output(account, batch_id, format="json")
    assert as_json.status_code == 200, as_json.text
    table = as_json.json()
    assert table["columns"] == ["name", "city", "total"]
    assert table["rows"] == [
        ["Ada", "London", "1"],
        ["Ben", "Paris", "2"],
        ["Cyd", "Rome", "3"],
        ["Dee", "Oslo", "4"],
        ["Eve", "Bern", "5"],
    ]

    as_csv = batch_output(account, batch_id, format="csv")
    assert as_csv.status_code == 200, as_csv.text
    assert "text/csv" in as_csv.headers["content-type"]
    parsed = list(csv.reader(io.StringIO(as_csv.text)))
    assert parsed[0] == ["name", "city", "total"]
    assert parsed[1:] == [
        ["Ada", "London", "1"],
        ["Ben", "Paris", "2"],
        ["Cyd", "Rome", "3"],
        ["Dee", "Oslo", "4"],
        ["Eve", "Bern", "5"],
    ]


def test_batch_row_events_stream_as_rows_change(
    new_account: NewAccount, live_origin: str
) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    batch_id = create_batch(
        account, workflow_id, name="Live", rows=five_rows()[:2]
    ).json()["batch_id"]
    first_id = current_run_id(account, batch_id)

    with (
        http_client(account, live_origin) as client,
        client.stream("GET", f"/api/batches/{batch_id}/events") as stream,
    ):
        assert stream.status_code == 200
        finish_run(first_id)
        on_terminal_run(UUID(first_id))
        events = parse_sse(stream.iter_lines(), 2)

    kinds = [event_type for event_type, _ in events]
    assert kinds == ["batch.row", "batch.row"]
    first, second = events[0][1], events[1][1]
    assert first["batch_id"] == batch_id
    assert first["row_index"] == 0
    assert first["status"] == "succeeded"
    assert first["run_id"] == first_id
    assert second["row_index"] == 1
    assert second["status"] == "running"
    assert second["run_id"] != first_id


def test_secret_values_never_travel_in_rows(new_account: NewAccount) -> None:
    account = new_account()
    secret = create_secret(account).json()
    workflow_id = a_workflow(account)
    saved = save_draft(
        account,
        workflow_id,
        steps=[a_navigate_step(str(uuid4()))],
        variables=[
            {"name": "name"},
            {
                "name": "password",
                "secret": True,
                "secretId": secret["id"],
                "secretName": secret["name"],
            },
        ],
    )
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201

    created = create_batch(
        account,
        workflow_id,
        name="Secrets",
        rows=[{"variables": {"name": "Ada", "password": "do-not-store"}}],
    )
    assert created.status_code == 201, created.text
    row = get_batch(account, created.json()["batch_id"]).json()["rows"][0]
    assert row["variables"] == {"name": "Ada"}
    run = account.client.get(f"/api/runs/{row['latest_run_id']}").json()
    assert run["run"]["variables"] == {"name": "Ada"}
    assert run["run"]["trigger"] == "batch"
    assert run["batch_row"]["index"] == 0
    assert run["batch_row"]["status"] == "running"


def test_another_organizations_batch_is_hidden(new_account: NewAccount) -> None:
    owner = new_account()
    stranger = new_account()
    workflow_id = workflow_with_name(owner)
    batch_id = create_batch(
        owner, workflow_id, name="Private", rows=five_rows()[:1]
    ).json()["batch_id"]

    assert (
        create_batch(stranger, workflow_id, name="X", rows=five_rows()[:1]).status_code
        == 404
    )
    assert get_batch(stranger, batch_id).status_code == 404
    assert batch_output(stranger, batch_id).status_code == 404
    assert stranger.client.post(f"/api/batches/{batch_id}/cancel").status_code == 404
    assert (
        stranger.client.post(f"/api/batches/{batch_id}/rows/0/skip").status_code == 404
    )
    assert (
        stranger.client.post(f"/api/batches/{batch_id}/rows/0/rerun").status_code == 404
    )
    assert list_batches(stranger, workflow_id=workflow_id).status_code == 404
    assert (
        stranger.client.patch(
            f"/api/batches/{batch_id}/rows/0", json={"variables": {"name": "x"}}
        ).status_code
        == 404
    )
    assert (
        stranger.client.post(
            f"/api/batches/{batch_id}/rows/fill",
            json={"name": "name", "value": "x"},
        ).status_code
        == 404
    )
    member = join(owner, stranger)
    assert get_batch(member, batch_id).status_code == 200


def test_creating_a_batch_requires_a_published_version(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    refused = create_batch(account, workflow_id, name="Draft", rows=[{"variables": {}}])
    assert refused.status_code == 409
    assert refused.json()["code"] == "no_published_version"
    assert (
        create_batch(
            account, published_workflow(account), name="Ok", rows=[]
        ).status_code
        == 201
    )


def test_incomplete_rows_are_skipped_unless_run_anyway(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = published_workflow(
        account, variables=[{"name": "name"}, {"name": "city"}]
    )
    rows = [
        {"variables": {"name": "Ada", "city": "London"}},
        {"variables": {"name": "Ben"}},
        {"variables": {"name": "Cyd", "city": "Rome"}},
    ]

    created = create_batch(account, workflow_id, name="Cities", rows=rows)
    assert created.status_code == 201, created.text
    body = get_batch(account, created.json()["batch_id"]).json()
    assert [row["status"] for row in body["rows"]] == [
        "running",
        "skipped",
        "queued",
    ]

    anyway = create_batch(
        account, workflow_id, name="Anyway", rows=rows, run_incomplete_rows=True
    )
    assert anyway.status_code == 201, anyway.text
    queued = get_batch(account, anyway.json()["batch_id"]).json()
    assert [row["status"] for row in queued["rows"]] == [
        "running",
        "queued",
        "queued",
    ]


def test_creating_a_batch_refuses_more_than_the_row_cap(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    refused = create_batch(
        account,
        workflow_id,
        name="Huge",
        rows=[{"variables": {"name": str(index)}} for index in range(1001)],
    )
    assert refused.status_code == 413
    assert refused.json()["code"] == "too_many_rows"
    assert refused.json()["max"] == 1000


def test_creating_a_batch_refuses_unknown_variables(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    refused = create_batch(
        account,
        workflow_id,
        name="Unknown",
        rows=[
            {"variables": {"city": "London", "town": "X"}},
            {"variables": {"county": "Y"}},
        ],
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "unknown_variable"
    assert refused.json()["names"] == ["county", "town"]


def test_patching_a_skipped_row_edits_values_not_status(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(
        account, variables=[{"name": "name"}, {"name": "city"}]
    )
    batch_id = create_batch(
        account,
        workflow_id,
        name="Fix",
        rows=[
            {"variables": {"name": "Ada", "city": "London"}},
            {"variables": {"name": "Ben"}},
        ],
    ).json()["batch_id"]
    finish_run(current_run_id(account, batch_id))
    on_terminal_run(UUID(current_run_id(account, batch_id)))

    patched = account.client.patch(
        f"/api/batches/{batch_id}/rows/1",
        json={"variables": {"name": "Ben", "city": "Paris"}},
    )
    assert patched.status_code == 200, patched.text
    row = patched.json()
    assert row["status"] == "skipped"
    assert row["variables"] == {"name": "Ben", "city": "Paris"}

    rerun = account.client.post(f"/api/batches/{batch_id}/rows/1/rerun")
    assert rerun.status_code == 201, rerun.text
    body = get_batch(account, batch_id).json()
    assert body["rows"][1]["status"] == "running"
    assert body["rows"][1]["latest_run_id"] == rerun.json()["run_id"]
    assert body["rows"][1]["variables"] == {"name": "Ben", "city": "Paris"}


def test_patching_a_running_succeeded_or_cancelled_row_is_refused(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    batch_id = create_batch(
        account, workflow_id, name="Locked", rows=five_rows()[:3]
    ).json()["batch_id"]

    running = account.client.patch(
        f"/api/batches/{batch_id}/rows/0", json={"variables": {"name": "x"}}
    )
    assert running.status_code == 409
    assert running.json()["code"] == "row_not_editable"

    finish_run(current_run_id(account, batch_id))
    on_terminal_run(UUID(current_run_id(account, batch_id)))
    succeeded = account.client.patch(
        f"/api/batches/{batch_id}/rows/0", json={"variables": {"name": "x"}}
    )
    assert succeeded.status_code == 409
    assert succeeded.json()["code"] == "row_not_editable"

    cancelled = account.client.post(f"/api/batches/{batch_id}/cancel")
    assert cancelled.status_code == 202, cancelled.text
    locked = account.client.patch(
        f"/api/batches/{batch_id}/rows/2", json={"variables": {"name": "x"}}
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "row_not_editable"


def test_fill_sets_one_variable_on_queued_rows_that_lack_it(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(
        account, variables=[{"name": "name"}, {"name": "region"}]
    )
    batch_id = create_batch(
        account,
        workflow_id,
        name="Fill",
        run_incomplete_rows=True,
        rows=[
            {"variables": {"name": "r0", "region": "keep"}},
            {"variables": {"name": "r1"}},
            {"variables": {"name": "r2", "region": "west"}},
            {"variables": {"name": "r3"}},
            {"variables": {"name": "r4", "region": "east"}},
            {"variables": {"name": "r5"}},
        ],
    ).json()["batch_id"]

    filled = account.client.post(
        f"/api/batches/{batch_id}/rows/fill", json={"name": "region", "value": "EU"}
    )
    assert filled.status_code == 200, filled.text
    assert filled.json() == {"updated_count": 3}

    rows = get_batch(account, batch_id).json()["rows"]
    assert rows[0]["status"] == "running"
    assert rows[0]["variables"] == {"name": "r0", "region": "keep"}
    assert rows[1]["variables"] == {"name": "r1", "region": "EU"}
    assert rows[2]["variables"] == {"name": "r2", "region": "west"}
    assert rows[3]["variables"] == {"name": "r3", "region": "EU"}
    assert rows[4]["variables"] == {"name": "r4", "region": "east"}
    assert rows[5]["variables"] == {"name": "r5", "region": "EU"}
    assert [row["status"] for row in rows[1:]] == ["queued"] * 5


def test_listing_batches_pages_summaries_with_derived_stats(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = workflow_with_name(account)
    other = workflow_with_name(account)
    seeded: list[str] = []
    for index in range(5):
        rows = five_rows()[:2] if index == 0 else five_rows()[:1]
        created = create_batch(account, workflow_id, name=f"B{index}", rows=rows)
        assert created.status_code == 201, created.text
        seeded.append(created.json()["batch_id"])
    assert (
        create_batch(account, other, name="Other", rows=five_rows()[:1]).status_code
        == 201
    )

    found: list[str] = []
    cursor = None
    while True:
        response = list_batches(
            account,
            workflow_id=workflow_id,
            limit=2,
            **({"cursor": cursor} if cursor else {}),
        )
        assert response.status_code == 200, response.text
        page = response.json()
        found.extend(item["id"] for item in page["items"])
        cursor = page.get("next_cursor")
        if cursor is None:
            break

    assert found == list(reversed(seeded))
    assert len(found) == len(set(found)) == 5

    first = list_batches(account, workflow_id=workflow_id, limit=1).json()["items"][0]
    assert first["id"] == seeded[-1]
    assert first["name"] == "B4"
    assert first["workflow_id"] == workflow_id
    assert first["cancelled_at"] is None
    assert first["row_count"] == 1
    assert first["stats"] == {
        "succeeded": 0,
        "failed": 0,
        "queued": 0,
        "skipped": 0,
        "cancelled": 0,
        "running": 1,
    }

    two_row = list_batches(account, workflow_id=workflow_id).json()["items"][-1]
    assert two_row["id"] == seeded[0]
    assert two_row["row_count"] == 2
    assert two_row["stats"]["running"] == 1
    assert two_row["stats"]["queued"] == 1
