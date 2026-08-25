"""Cancellation and the Worker's control read at the HTTP seam."""

import json
import time
from uuid import UUID

import pytest
from step_by_step_api import clock
from step_by_step_api.runs.models import Run, RunStatus
from step_by_step_core.bus import control_channel, get_redis
from step_by_step_core.db import session_scope
from step_by_step_worker.control import ControlWatch, flags_from_row
from test_heartbeats import TOKEN, claimed_run
from test_runs import detail
from test_workflows import NewAccount

pytestmark = pytest.mark.integration
DISPATCH_LIST = "runs:dispatch"


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", TOKEN)


def read_control(client, run_id: str, *, token: str | None = TOKEN):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return client.get(f"/internal/runs/{run_id}/control", headers=headers)


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


def test_cancelling_a_running_run_stamps_the_request_and_stays_running(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)

    cancelled = account.client.post(f"/api/runs/{run_id}/cancel")

    assert cancelled.status_code == 202
    row = detail(account, run_id).json()["run"]
    assert row["status"] == "running"
    assert row["cancel_requested_at"] is not None


def test_cancelling_a_terminal_run_is_rejected(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = RunStatus.SUCCEEDED
        db.commit()

    refused = account.client.post(f"/api/runs/{run_id}/cancel")

    assert refused.status_code == 409
    assert refused.json()["code"] == "run_terminal"


def test_internal_control_read_requires_the_shared_token(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)

    refused = read_control(account.client, run_id, token=None)

    assert refused.status_code == 401


def test_internal_control_read_reflects_the_row_flags(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    assert account.client.post(f"/api/runs/{run_id}/cancel").status_code == 202

    flags = read_control(account.client, run_id)

    assert flags.status_code == 200, flags.text
    assert flags.json() == {
        "cancel_requested": True,
        "pause_requested": False,
        "takeover_phase": None,
        "auto_handback_disabled": False,
    }


def test_cancelling_a_running_run_publishes_on_its_control_channel(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    channel = f"run:{run_id}:control"
    pubsub = get_redis().pubsub(ignore_subscribe_messages=False)
    pubsub.subscribe(channel)
    ack = pubsub.get_message(timeout=1.0)
    assert ack is not None and ack["type"] == "subscribe"

    assert account.client.post(f"/api/runs/{run_id}/cancel").status_code == 202

    message = pubsub.get_message(timeout=1.0)
    pubsub.close()
    assert message is not None
    assert message["type"] == "message"
    raw = message["data"]
    if isinstance(raw, bytes):
        raw = raw.decode()
    assert json.loads(raw) == {"cancel_requested": True}


def test_a_cancel_written_to_the_row_is_visible_without_a_publish(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    channel = f"run:{run_id}:control"
    pubsub = get_redis().pubsub(ignore_subscribe_messages=False)
    pubsub.subscribe(channel)
    assert pubsub.get_message(timeout=1.0)["type"] == "subscribe"
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.cancel_requested_at = clock.now()
        db.commit()

    flags = flags_from_row(UUID(run_id))
    message = pubsub.get_message(timeout=0.2)
    pubsub.close()

    assert flags.cancel_requested is True
    assert message is None


def test_the_worker_honors_a_control_message_when_it_arrives(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = UUID(claimed_run(account))
    watch = ControlWatch(run_id)
    try:
        get_redis().publish(
            control_channel(run_id), json.dumps({"cancel_requested": True})
        )
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and not watch.poll().cancel_requested:
            time.sleep(0.05)
        assert watch.poll().cancel_requested is True
    finally:
        watch.close()
