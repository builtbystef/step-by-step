"""Takeover control: pause, tickets, hand-back, abandon, deadline, cancel."""

import json
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from step_by_step_api import clock
from step_by_step_api.accounts.sessions import SESSION_COOKIE, token_digest
from step_by_step_api.loop import tick
from step_by_step_api.runs.models import Run, RunStatus
from step_by_step_api.runs.tickets import redeem_ticket
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from step_by_step_worker.store import PostgresRunStore
from test_heartbeats import TOKEN, claimed_run, three_step_workflow
from test_runs import detail, start
from test_sessions import another_device
from test_workflows import NewAccount

pytestmark = pytest.mark.integration
DISPATCH_LIST = "runs:dispatch"


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", TOKEN)


def org_session(account) -> TestClient:
    """The same person, a second browser, acting in the same Organization."""
    browser = another_device(account)
    browser.headers["X-Organization"] = account.org_id
    return browser


def park(
    run_id: str,
    *,
    deadline_in: timedelta = timedelta(minutes=30),
    holder: str | None = None,
) -> None:
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.takeover_deadline_at = clock.now() + deadline_in
        run.takeover_holder_session_id = holder
        db.commit()


def claimed_steps(account) -> tuple[str, list[str]]:
    workflow_id, step_ids = three_step_workflow(account)
    run_id = start(account, workflow_id, variables={}).json()["run_id"]
    assert (
        PostgresRunStore().claim(UUID(run_id), "worker-1", "worker-1:5900", clock.now())
        is not None
    )
    return run_id, step_ids


def test_pausing_a_running_run_stamps_the_request(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)

    paused = account.client.post(f"/api/runs/{run_id}/pause")

    assert paused.status_code == 202
    row = detail(account, run_id).json()["run"]
    assert row["status"] == "running"
    assert row["pause_requested_at"] is not None


def test_takeover_on_a_running_run_is_not_waiting(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)

    refused = account.client.post(f"/api/runs/{run_id}/takeover")

    assert refused.status_code == 409
    assert refused.json()["code"] == "not_waiting"


def test_takeover_on_a_waiting_run_mints_a_ticket(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)

    taken = account.client.post(f"/api/runs/{run_id}/takeover")

    assert taken.status_code == 200, taken.text
    body = taken.json()
    assert body["ticket"]
    assert body["ws_url"].endswith(f"/api/runs/{run_id}/vnc?ticket={body['ticket']}")
    assert body["expires_at"] is not None
    assert body["deadline_at"] is not None
    row = detail(account, run_id).json()["run"]
    assert row["status"] == "waiting_for_human"
    assert datetime_of(row["takeover_deadline_at"]) == datetime_of(body["deadline_at"])


def test_a_second_session_cannot_take_a_held_run(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)
    assert account.client.post(f"/api/runs/{run_id}/takeover").status_code == 200
    other = org_session(account)

    refused = other.post(f"/api/runs/{run_id}/takeover")

    assert refused.status_code == 409
    assert refused.json()["code"] == "already_held"


def test_a_ticket_is_refused_the_second_time_it_is_redeemed(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)
    ticket = account.client.post(f"/api/runs/{run_id}/takeover").json()["ticket"]

    with session_scope() as db:
        first = redeem_ticket(db, ticket)
        db.commit()
    with session_scope() as db:
        second = redeem_ticket(db, ticket)
        db.commit()

    assert first is not None and first.run_id == UUID(run_id)
    assert second is None


def test_handback_stamps_the_request_on_a_held_run(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)
    assert account.client.post(f"/api/runs/{run_id}/takeover").status_code == 200

    handed = account.client.post(f"/api/runs/{run_id}/handback")

    assert handed.status_code == 202
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        assert run.handback_requested_at is not None
        assert run.status is RunStatus.WAITING_FOR_HUMAN


def test_abandon_fails_the_paused_step_and_skips_the_rest(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id, step_ids = claimed_steps(account)
    park(run_id)
    assert account.client.post(f"/api/runs/{run_id}/takeover").status_code == 200

    abandoned = account.client.post(f"/api/runs/{run_id}/takeover/abandon")

    assert abandoned.status_code == 202
    row = detail(account, run_id).json()
    assert row["run"]["status"] == "failed"
    assert row["run"]["failure_reason"] == "takeover_abandoned"
    assert [result["status"] for result in row["step_results"]] == [
        "failed",
        "skipped",
        "skipped",
    ]
    assert [result["step_id"] for result in row["step_results"]] == step_ids


def test_a_waiting_run_past_its_deadline_is_reaped_as_takeover_timeout(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id, step_ids = claimed_steps(account)
    park(run_id, deadline_in=timedelta(seconds=-1))

    tick()

    row = detail(account, run_id).json()
    assert row["run"]["status"] == "failed"
    assert row["run"]["failure_reason"] == "takeover_timeout"
    assert [result["status"] for result in row["step_results"]] == [
        "failed",
        "skipped",
        "skipped",
    ]
    assert [result["step_id"] for result in row["step_results"]] == step_ids


def test_a_held_run_past_its_deadline_is_reaped_the_same_way(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(
        run_id,
        deadline_in=timedelta(seconds=-1),
        holder=token_digest(account.client.cookies[SESSION_COOKIE]),
    )

    tick()

    row = detail(account, run_id).json()["run"]
    assert row["status"] == "failed"
    assert row["failure_reason"] == "takeover_timeout"


def test_cancelling_a_waiting_run_is_immediate(new_account: NewAccount) -> None:
    account = new_account()
    run_id, step_ids = claimed_steps(account)
    park(run_id)

    cancelled = account.client.post(f"/api/runs/{run_id}/cancel")

    assert cancelled.status_code == 202
    row = detail(account, run_id).json()
    assert row["run"]["status"] == "cancelled"
    assert row["run"]["ended_at"] is not None
    assert [result["status"] for result in row["step_results"]] == [
        "skipped",
        "skipped",
        "skipped",
    ]
    assert [result["step_id"] for result in row["step_results"]] == step_ids


def test_pausing_publishes_on_the_control_channel(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    channel = f"run:{run_id}:control"
    pubsub = get_redis().pubsub(ignore_subscribe_messages=False)
    pubsub.subscribe(channel)
    ack = pubsub.get_message(timeout=1.0)
    assert ack is not None and ack["type"] == "subscribe"

    assert account.client.post(f"/api/runs/{run_id}/pause").status_code == 202

    message = pubsub.get_message(timeout=1.0)
    pubsub.close()
    assert message is not None
    raw = message["data"]
    if isinstance(raw, bytes):
        raw = raw.decode()
    assert json.loads(raw) == {"pause_requested": True}


def test_hold_disables_auto_handback_on_a_held_run(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)
    taken = account.client.post(f"/api/runs/{run_id}/takeover")
    assert taken.status_code == 200
    deadline = taken.json()["deadline_at"]

    held = account.client.post(
        f"/api/runs/{run_id}/takeover/hold", json={"auto_handback": False}
    )

    assert held.status_code == 204, held.text
    row = detail(account, run_id).json()["run"]
    assert row["auto_handback_disabled"] is True
    assert row["takeover_deadline_at"] == deadline
    flags = account.client.get(
        f"/internal/runs/{run_id}/control",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert flags.status_code == 200
    assert flags.json()["auto_handback_disabled"] is True


def test_hold_on_a_running_run_is_not_waiting(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)

    refused = account.client.post(
        f"/api/runs/{run_id}/takeover/hold", json={"auto_handback": False}
    )

    assert refused.status_code == 409
    assert refused.json()["code"] == "not_waiting"


def test_hold_without_control_is_not_held(new_account: NewAccount) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)

    refused = account.client.post(
        f"/api/runs/{run_id}/takeover/hold", json={"auto_handback": False}
    )

    assert refused.status_code == 409
    assert refused.json()["code"] == "not_held"


def test_a_waiting_run_can_be_taken_again_after_the_holder_is_released(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    park(run_id)
    first = account.client.post(f"/api/runs/{run_id}/takeover")
    assert first.status_code == 200
    deadline = first.json()["deadline_at"]
    PostgresRunStore().release_holder(UUID(run_id), clock.now())

    second = account.client.post(f"/api/runs/{run_id}/takeover")

    assert second.status_code == 200, second.text
    row = detail(account, run_id).json()["run"]
    assert row["status"] == "waiting_for_human"
    assert row["auto_handback_disabled"] is False
    assert row["takeover_deadline_at"] == deadline


def datetime_of(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)
