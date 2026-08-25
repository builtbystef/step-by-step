"""The Schedule store and the minute tick: HTTP against Postgres and Redis."""

from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from conftest import Account
from step_by_step_api import clock
from step_by_step_api.loop import tick
from step_by_step_api.runs.models import Run, RunStatus
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from test_runs import published_workflow
from test_workflow_versions import publish
from test_workflows import NewAccount, a_navigate_step, save_draft

pytestmark = pytest.mark.integration
BELGRADE = ZoneInfo("Europe/Belgrade")
DISPATCH_LIST = "runs:dispatch"


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


def create_schedule(account: Account, workflow_id: str, **body: object):
    return account.client.post(f"/api/workflows/{workflow_id}/schedules", json=body)


def list_schedules(account: Account, workflow_id: str):
    return account.client.get(f"/api/workflows/{workflow_id}/schedules")


def test_post_refuses_a_broken_cron_or_timezone(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = published_workflow(account)

    bad_cron = create_schedule(
        account,
        workflow_id,
        cron="not a cron",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    bad_zone = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Mars/Olympus",
        enabled=True,
    )

    assert bad_cron.status_code == 400
    assert bad_cron.json()["code"] == "invalid_cron"
    assert bad_zone.status_code == 400
    assert bad_zone.json()["code"] == "invalid_timezone"


def freeze(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(clock, "now", lambda: when)


def runs_of(account: Account, workflow_id: str) -> list[dict[str, object]]:
    listed = account.client.get("/api/runs", params={"workflow_id": workflow_id})
    assert listed.status_code == 200, listed.text
    return list(listed.json()["items"])


def test_two_ticks_across_nine_create_one_local_run(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text

    tick()
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE))
    tick()
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 1, tzinfo=BELGRADE))
    tick()

    fired = runs_of(account, workflow_id)
    assert len(fired) == 1
    assert fired[0]["trigger"] == "schedule"
    queued = [
        value.decode() if isinstance(value, bytes) else value
        for value in get_redis().lrange(DISPATCH_LIST, 0, -1)
    ]
    assert queued == [fired[0]["id"]]
    due = datetime.fromisoformat(
        list_schedules(account, workflow_id).json()[0]["next_due_at"]
    )
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE)


def test_a_still_running_run_skips_the_next_occurrence(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE))
    tick()
    run_id = UUID(str(runs_of(account, workflow_id)[0]["id"]))
    with session_scope() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = RunStatus.RUNNING
        db.commit()

    freeze(monkeypatch, datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE))
    tick()

    assert len(runs_of(account, workflow_id)) == 1
    schedule = list_schedules(account, workflow_id).json()[0]
    assert schedule["last_skip_reason"] == "overlap"
    due = datetime.fromisoformat(schedule["next_due_at"])
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 27, 9, 0, tzinfo=BELGRADE)


def test_a_six_hour_gap_creates_no_catch_up_runs(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 30, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 */2 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text
    assert datetime.fromisoformat(created.json()["next_due_at"]).astimezone(
        BELGRADE
    ) == datetime(2026, 8, 25, 10, 0, tzinfo=BELGRADE)

    later = datetime(2026, 8, 25, 15, 30, tzinfo=BELGRADE)
    freeze(monkeypatch, later)
    tick()

    assert runs_of(account, workflow_id) == []
    due = datetime.fromisoformat(
        list_schedules(account, workflow_id).json()[0]["next_due_at"]
    )
    assert due > later
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 25, 16, 0, tzinfo=BELGRADE)


def test_a_disabled_schedule_does_not_fire_and_reenable_skips_missed(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=False,
    )
    assert created.status_code == 201, created.text
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE))
    tick()
    assert runs_of(account, workflow_id) == []

    freeze(monkeypatch, datetime(2026, 8, 25, 15, 0, tzinfo=BELGRADE))
    updated = account.client.patch(
        f"/api/schedules/{created.json()['id']}", json={"enabled": True}
    )
    assert updated.status_code == 200, updated.text
    due = datetime.fromisoformat(updated.json()["next_due_at"])
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE)
    tick()
    assert runs_of(account, workflow_id) == []


def test_a_fired_run_uses_the_latest_published_version(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text
    assert (
        save_draft(
            account, workflow_id, steps=[a_navigate_step(str(uuid4()))]
        ).status_code
        == 200
    )
    assert publish(account, workflow_id).status_code == 201

    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE))
    tick()

    fired = runs_of(account, workflow_id)
    assert len(fired) == 1
    assert fired[0]["version_number"] == 2


def test_schedule_routes_hide_another_organizations_schedule(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()
    workflow_id = published_workflow(owner)
    created = create_schedule(
        owner,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]

    assert list_schedules(stranger, workflow_id).status_code == 404
    assert (
        create_schedule(
            stranger,
            workflow_id,
            cron="0 10 * * *",
            timezone="UTC",
            enabled=True,
        ).status_code
        == 404
    )
    assert (
        stranger.client.patch(
            f"/api/schedules/{schedule_id}", json={"enabled": False}
        ).status_code
        == 404
    )
    assert stranger.client.delete(f"/api/schedules/{schedule_id}").status_code == 404
    assert list_schedules(owner, workflow_id).status_code == 200


def test_delete_removes_the_schedule(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text

    deleted = account.client.delete(f"/api/schedules/{created.json()['id']}")

    assert deleted.status_code == 204
    assert list_schedules(account, workflow_id).json() == []
