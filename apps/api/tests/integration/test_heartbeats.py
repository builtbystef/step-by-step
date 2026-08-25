"""Heartbeats, reaping, and the queue backstop at the HTTP and tick seams."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from step_by_step_api import clock
from step_by_step_api.loop import tick
from step_by_step_api.runs.models import Run, RunStatus, StepResult, StepResultStatus
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from step_by_step_worker.store import PostgresRunStore
from test_runs import detail, published_workflow, start
from test_workflow_versions import publish
from test_workflows import NewAccount, a_navigate_step, a_workflow, save_draft

pytestmark = pytest.mark.integration
DISPATCH_LIST = "runs:dispatch"
TOKEN = "test-internal-token"


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", TOKEN)


def heartbeat(client, run_id: str, *, token: str | None = TOKEN, **body: object):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return client.post(
        f"/internal/runs/{run_id}/heartbeat",
        json={"worker_id": "worker-1", "vnc_endpoint": "worker-1:5900", **body},
        headers=headers,
    )


def test_heartbeat_without_the_shared_token_is_refused(new_account: NewAccount) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]

    refused = heartbeat(account.client, run_id, token=None)

    assert refused.status_code == 401


def claimed_run(account) -> str:
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    work = PostgresRunStore().claim(
        UUID(run_id), "worker-1", "worker-1:5900", clock.now()
    )
    assert work is not None
    return run_id


def freeze(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(clock, "now", lambda: when)


def test_heartbeat_advances_the_run_row(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    first = datetime.fromisoformat(
        detail(account, run_id).json()["run"]["heartbeat_at"]
    )
    later = first + timedelta(seconds=5)
    freeze(monkeypatch, later)

    beaten = heartbeat(account.client, run_id)

    assert beaten.status_code == 204, beaten.text
    row = detail(account, run_id).json()["run"]
    assert datetime.fromisoformat(row["heartbeat_at"]) == later
    assert row["worker_id"] == "worker-1"
    assert row["worker_vnc_endpoint"] == "worker-1:5900"


def test_heartbeat_on_a_terminal_run_is_run_terminal(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = RunStatus.SUCCEEDED
        db.commit()

    refused = heartbeat(account.client, run_id)

    assert refused.status_code == 409
    assert refused.json()["code"] == "run_terminal"


def three_step_workflow(account) -> tuple[str, list[str]]:
    workflow_id = a_workflow(account)
    step_ids = [str(uuid4()) for _ in range(3)]
    saved = save_draft(
        account,
        workflow_id,
        steps=[a_navigate_step(step_id) for step_id in step_ids],
    )
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201
    return workflow_id, step_ids


def test_a_stale_heartbeat_is_reaped_as_worker_lost(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id, step_ids = three_step_workflow(account)
    run_id = start(account, workflow_id, variables={}).json()["run_id"]
    claimed_at = clock.now() - timedelta(hours=1)
    assert (
        PostgresRunStore().claim(UUID(run_id), "worker-1", "worker-1:5900", claimed_at)
        is not None
    )
    with session_scope() as db:
        db.add(
            StepResult(
                run_id=UUID(run_id),
                step_id=UUID(step_ids[0]),
                position=0,
                status=StepResultStatus.PASSED,
            )
        )
        db.commit()

    tick()

    row = detail(account, run_id).json()
    assert row["run"]["status"] == "failed"
    assert row["run"]["failure_reason"] == "worker_lost"
    results = row["step_results"]
    assert [result["position"] for result in results] == [0, 1, 2]
    assert [result["status"] for result in results] == ["passed", "skipped", "skipped"]
    assert [result["step_id"] for result in results] == step_ids


def test_a_healthy_running_run_is_untouched_by_a_tick(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_run(account)
    before = detail(account, run_id).json()["run"]

    tick()

    after = detail(account, run_id).json()["run"]
    assert after["status"] == "running"
    assert after["failure_reason"] is None
    assert after["heartbeat_at"] == before["heartbeat_at"]
    assert after["ended_at"] is None


def queued_ids() -> list[str]:
    return [
        value.decode() if isinstance(value, bytes) else value
        for value in get_redis().lrange(DISPATCH_LIST, 0, -1)
    ]


def age_queued(run_id: str, *, hours: int = 1) -> None:
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.queued_at = clock.now() - timedelta(hours=hours)
        db.commit()


def test_a_stale_queued_run_is_put_back_on_the_list(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    get_redis().delete(DISPATCH_LIST)
    age_queued(run_id)

    tick()

    assert run_id in queued_ids()
    assert detail(account, run_id).json()["run"]["status"] == "queued"


def test_a_fresh_queued_run_is_left_off_the_list(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    get_redis().delete(DISPATCH_LIST)

    tick()

    assert run_id not in queued_ids()
    assert detail(account, run_id).json()["run"]["status"] == "queued"


def test_a_duplicate_re_enqueued_id_is_claimed_once(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    get_redis().delete(DISPATCH_LIST)
    age_queued(run_id)
    tick()
    tick()
    store = PostgresRunStore()

    first = store.claim(UUID(run_id), "worker-1", "worker-1:5900", clock.now())
    second = store.claim(UUID(run_id), "worker-2", "worker-2:5900", clock.now())

    assert first is not None
    assert second is None
    assert queued_ids().count(run_id) == 2
