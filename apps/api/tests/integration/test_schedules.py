"""The Schedule store and the minute tick: HTTP against Postgres and Redis."""

from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from conftest import Account
from sqlalchemy import select
from step_by_step_api import clock
from step_by_step_api.loop import tick
from step_by_step_api.runs.models import Run, RunStatus
from step_by_step_api.schedules.models import ScheduleOccurrence
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from test_runs import published_workflow
from test_workflow_versions import publish
from test_workflows import NewAccount, a_navigate_step, a_workflow, save_draft

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


def schedule_of(account: Account, workflow_id: str) -> dict[str, object]:
    listed = list_schedules(account, workflow_id)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 1
    return dict(rows[0])


def holes_of(schedule_id: str) -> list[ScheduleOccurrence]:
    with session_scope() as db:
        rows = db.execute(
            select(ScheduleOccurrence)
            .where(ScheduleOccurrence.schedule_id == UUID(schedule_id))
            .order_by(ScheduleOccurrence.occurrence_at)
        ).scalars()
        return list(rows)


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
    schedule = schedule_of(account, workflow_id)
    hole = schedule["latest_occurrence"]
    assert isinstance(hole, dict)
    assert hole["reason"] == "overlap"
    assert hole["blocking_run_id"] == str(run_id)
    assert datetime.fromisoformat(str(hole["occurrence_at"])).astimezone(
        BELGRADE
    ) == datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE)
    due = datetime.fromisoformat(str(schedule["next_due_at"]))
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
        enabled=True,
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]
    paused = account.client.patch(
        f"/api/schedules/{schedule_id}", json={"enabled": False}
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["next_due_at"] is None

    for day in (25, 26, 27):
        freeze(monkeypatch, datetime(2026, 8, day, 9, 0, 45, tzinfo=BELGRADE))
        tick()
    assert runs_of(account, workflow_id) == []
    assert holes_of(schedule_id) == []

    freeze(monkeypatch, datetime(2026, 8, 27, 15, 0, tzinfo=BELGRADE))
    updated = account.client.patch(
        f"/api/schedules/{schedule_id}", json={"enabled": True}
    )
    assert updated.status_code == 200, updated.text
    due = datetime.fromisoformat(updated.json()["next_due_at"])
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 28, 9, 0, tzinfo=BELGRADE)
    tick()
    assert runs_of(account, workflow_id) == []
    assert holes_of(schedule_id) == []
    assert updated.json()["latest_occurrence"] is None


def test_tick_within_grace_creates_a_run_and_no_hole(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={"city": "Belgrade"},
    )
    assert created.status_code == 201, created.text
    assert "last_skip_reason" not in created.json()

    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, 45, tzinfo=BELGRADE))
    tick()

    fired = runs_of(account, workflow_id)
    assert len(fired) == 1
    assert fired[0]["trigger"] == "schedule"
    detail = account.client.get(f"/api/runs/{fired[0]['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["run"]["variables"] == {"city": "Belgrade"}
    schedule = schedule_of(account, workflow_id)
    assert schedule["latest_occurrence"] is None
    assert "last_skip_reason" not in schedule
    assert holes_of(str(created.json()["id"])) == []
    due = datetime.fromisoformat(str(schedule["next_due_at"]))
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE)


def test_tick_past_grace_records_missed_and_creates_no_run(
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

    freeze(monkeypatch, datetime(2026, 8, 25, 9, 4, tzinfo=BELGRADE))
    tick()

    assert runs_of(account, workflow_id) == []
    schedule = schedule_of(account, workflow_id)
    hole = schedule["latest_occurrence"]
    assert isinstance(hole, dict)
    assert hole["reason"] == "missed"
    assert hole["blocking_run_id"] is None
    assert datetime.fromisoformat(str(hole["occurrence_at"])).astimezone(
        BELGRADE
    ) == datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE)
    due = datetime.fromisoformat(str(schedule["next_due_at"]))
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE)


def test_an_hourly_schedule_records_six_missed_hours(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 * * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]
    assert datetime.fromisoformat(created.json()["next_due_at"]).astimezone(
        BELGRADE
    ) == datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE)

    freeze(monkeypatch, datetime(2026, 8, 25, 14, 30, tzinfo=BELGRADE))
    tick()

    assert runs_of(account, workflow_id) == []
    holes = holes_of(schedule_id)
    assert len(holes) == 6
    assert [hole.reason for hole in holes] == ["missed"] * 6
    assert [hole.occurrence_at.astimezone(BELGRADE) for hole in holes] == [
        datetime(2026, 8, 25, hour, 0, tzinfo=BELGRADE) for hour in range(9, 15)
    ]
    due = datetime.fromisoformat(str(schedule_of(account, workflow_id)["next_due_at"]))
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 25, 15, 0, tzinfo=BELGRADE)


def test_needs_values_records_a_hole_and_fires_after_the_value_is_set(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={"city": "Belgrade"},
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]
    assert (
        save_draft(
            account,
            workflow_id,
            steps=[a_navigate_step(str(uuid4()))],
            variables=[{"name": "city"}, {"name": "region"}],
        ).status_code
        == 200
    )
    assert publish(account, workflow_id).status_code == 201

    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, 45, tzinfo=BELGRADE))
    tick()

    assert runs_of(account, workflow_id) == []
    hole = schedule_of(account, workflow_id)["latest_occurrence"]
    assert isinstance(hole, dict)
    assert hole["reason"] == "missing_values"
    due = datetime.fromisoformat(str(schedule_of(account, workflow_id)["next_due_at"]))
    assert due.astimezone(BELGRADE) == datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE)

    patched = account.client.patch(
        f"/api/schedules/{schedule_id}",
        json={"variables": {"city": "Belgrade", "region": "EU"}},
    )
    assert patched.status_code == 200, patched.text
    freeze(monkeypatch, datetime(2026, 8, 26, 9, 0, 45, tzinfo=BELGRADE))
    tick()

    fired = runs_of(account, workflow_id)
    assert len(fired) == 1
    assert fired[0]["trigger"] == "schedule"


def test_nine_am_belgrade_fires_at_the_utc_instants_across_october_dst(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, datetime(2026, 10, 24, 8, 59, tzinfo=BELGRADE))
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

    freeze(monkeypatch, datetime(2026, 10, 24, 9, 0, tzinfo=BELGRADE))
    tick()
    first = schedule_of(account, workflow_id)
    assert datetime.fromisoformat(str(first["last_fired_at"])) == datetime(
        2026, 10, 24, 7, 0, tzinfo=ZoneInfo("UTC")
    )
    run_id = UUID(str(runs_of(account, workflow_id)[0]["id"]))
    with session_scope() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = RunStatus.SUCCEEDED
        db.commit()

    freeze(monkeypatch, datetime(2026, 10, 25, 9, 0, tzinfo=BELGRADE))
    tick()
    second = schedule_of(account, workflow_id)
    assert datetime.fromisoformat(str(second["last_fired_at"])) == datetime(
        2026, 10, 25, 8, 0, tzinfo=ZoneInfo("UTC")
    )
    assert len(runs_of(account, workflow_id)) == 2
    assert holes_of(str(created.json()["id"])) == []


def test_occurrence_rows_are_pruned_to_the_most_recent_500(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    freeze(monkeypatch, datetime(2026, 8, 4, 18, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 * * * *",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]

    freeze(monkeypatch, datetime(2026, 8, 25, 14, 30, tzinfo=BELGRADE))
    tick()
    assert len(holes_of(schedule_id)) == 500

    freeze(monkeypatch, datetime(2026, 8, 25, 20, 30, tzinfo=BELGRADE))
    tick()
    holes = holes_of(schedule_id)
    assert len(holes) == 500
    assert holes[0].occurrence_at.astimezone(BELGRADE) == datetime(
        2026, 8, 5, 1, 0, tzinfo=BELGRADE
    )
    assert holes[-1].occurrence_at.astimezone(BELGRADE) == datetime(
        2026, 8, 25, 20, 0, tzinfo=BELGRADE
    )
    assert {hole.reason for hole in holes} == {"missed"}


def test_deleting_a_schedule_deletes_its_occurrence_rows(
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
    schedule_id = created.json()["id"]
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 4, tzinfo=BELGRADE))
    tick()
    assert len(holes_of(schedule_id)) == 1

    deleted = account.client.delete(f"/api/schedules/{schedule_id}")
    assert deleted.status_code == 204
    assert holes_of(schedule_id) == []


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
    assert schedule_detail(stranger, schedule_id).status_code == 404
    assert run_now(stranger, schedule_id).status_code == 404
    listed = list_all_schedules(stranger)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    assert list_all_schedules(stranger, workflow_id=workflow_id).status_code == 404
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


def test_post_requires_every_non_secret_variable_and_rejects_secrets(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(
        account,
        variables=[{"name": "city"}, {"name": "password", "secret": True}],
    )

    refused = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={},
    )
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={"city": "Belgrade", "password": "do-not-store"},
    )

    assert refused.status_code == 400
    body = refused.json()
    assert body["code"] == "missing_variable_values"
    assert body["variable_names"] == ["city"]
    assert created.status_code == 201, created.text
    assert created.json()["variables"] == {"city": "Belgrade"}


def test_patch_refuses_a_value_set_that_drops_a_required_variable(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={"city": "Belgrade"},
    )
    assert created.status_code == 201, created.text

    dropped = account.client.patch(
        f"/api/schedules/{created.json()['id']}", json={"variables": {}}
    )

    assert dropped.status_code == 400
    assert dropped.json()["code"] == "missing_variable_values"
    assert dropped.json()["variable_names"] == ["city"]


def test_post_refuses_a_workflow_with_no_published_version(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)

    refused = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={},
    )

    assert refused.status_code == 409
    assert refused.json()["code"] == "no_published_version"


def test_a_new_variable_derives_needs_values_until_patched(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={"city": "Belgrade"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["state"] == "active"
    assert created.json()["missing_variable_names"] == []

    assert (
        save_draft(
            account,
            workflow_id,
            steps=[a_navigate_step(str(uuid4()))],
            variables=[{"name": "city"}, {"name": "region"}],
        ).status_code
        == 200
    )
    assert publish(account, workflow_id).status_code == 201

    listed = list_schedules(account, workflow_id).json()[0]
    assert listed["state"] == "needs_values"
    assert listed["missing_variable_names"] == ["region"]
    assert listed["variables"] == {"city": "Belgrade"}

    patched = account.client.patch(
        f"/api/schedules/{created.json()['id']}",
        json={"variables": {"city": "Belgrade", "region": "EU"}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["state"] == "active"
    assert patched.json()["missing_variable_names"] == []
    assert patched.json()["variables"] == {"city": "Belgrade", "region": "EU"}


def test_a_disabled_schedule_reads_paused_even_when_values_are_missing(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=False,
        variables={"city": "Belgrade"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["state"] == "paused"

    assert (
        save_draft(
            account,
            workflow_id,
            steps=[a_navigate_step(str(uuid4()))],
            variables=[{"name": "city"}, {"name": "region"}],
        ).status_code
        == 200
    )
    assert publish(account, workflow_id).status_code == 201

    listed = list_schedules(account, workflow_id).json()[0]
    assert listed["state"] == "paused"
    assert listed["state"] != "needs_values"
    assert listed["missing_variable_names"] == ["region"]


def test_a_fired_run_carries_the_schedule_variables_at_fire_time(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={"city": "Belgrade"},
    )
    assert created.status_code == 201, created.text
    patched = account.client.patch(
        f"/api/schedules/{created.json()['id']}",
        json={"variables": {"city": "Novi Sad"}},
    )
    assert patched.status_code == 200, patched.text

    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE))
    tick()

    fired = runs_of(account, workflow_id)
    assert len(fired) == 1
    detail = account.client.get(f"/api/runs/{fired[0]['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["run"]["variables"] == {"city": "Novi Sad"}


def test_a_schedule_name_is_stored_patchable_and_nullable(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        name="Weekday invoices",
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Weekday invoices"

    renamed = account.client.patch(
        f"/api/schedules/{created.json()['id']}", json={"name": "Month-end"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Month-end"

    cleared = account.client.patch(
        f"/api/schedules/{created.json()['id']}", json={"name": None}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["name"] is None
    assert list_schedules(account, workflow_id).json()[0]["name"] is None


def preview(account: Account, **body: object):
    return account.client.post("/api/schedules/preview", json=body)


def test_preview_returns_five_deterministic_timestamps_without_a_schedule(
    new_account: NewAccount,
) -> None:
    account = new_account()
    assert list_schedules(account, a_workflow(account)).json() == []

    previewed = preview(
        account,
        cron="*/7 3-5 * * *",
        timezone="UTC",
        **{"from": "2026-01-15T00:00:00+00:00"},
    )

    assert previewed.status_code == 200, previewed.text
    stamps = previewed.json()["next_occurrences"]
    assert len(stamps) == 5
    assert [datetime.fromisoformat(stamp) for stamp in stamps] == [
        datetime(2026, 1, 15, 3, minute, tzinfo=ZoneInfo("UTC"))
        for minute in (0, 7, 14, 21, 28)
    ]


def test_preview_refuses_a_broken_cron_or_timezone(new_account: NewAccount) -> None:
    account = new_account()

    bad_cron = preview(account, cron="0 9 * * 8", timezone="UTC")
    bad_zone = preview(account, cron="0 9 * * *", timezone="Mars/Olympus")

    assert bad_cron.status_code == 400
    assert bad_cron.json()["code"] == "invalid_cron"
    assert bad_zone.status_code == 400
    assert bad_zone.json()["code"] == "invalid_timezone"


def list_all_schedules(account: Account, **params: object):
    return account.client.get("/api/schedules", params=params)


def test_the_instance_list_returns_every_schedule_with_derived_fields(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    invoices = published_workflow(account)
    payroll = a_workflow(account, name="Payroll")
    assert (
        save_draft(account, payroll, steps=[a_navigate_step(str(uuid4()))]).status_code
        == 200
    )
    assert publish(account, payroll).status_code == 201
    freeze(monkeypatch, datetime(2026, 8, 25, 8, 59, tzinfo=BELGRADE))
    first = create_schedule(
        account,
        invoices,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        name="Morning",
    )
    second = create_schedule(
        account,
        payroll,
        cron="0 10 * * *",
        timezone="UTC",
        enabled=False,
        name="Paused payroll",
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 4, tzinfo=BELGRADE))
    tick()

    listed = list_all_schedules(account)
    assert listed.status_code == 200, listed.text
    page = listed.json()
    rows = page["items"]
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {first.json()["id"], second.json()["id"]}

    morning = by_id[first.json()["id"]]
    assert morning["workflow_id"] == invoices
    assert morning["workflow_name"] == "Invoices"
    assert morning["name"] == "Morning"
    assert morning["cron"] == "0 9 * * *"
    assert morning["timezone"] == "Europe/Belgrade"
    assert morning["enabled"] is True
    assert morning["state"] == "active"
    assert morning["missing_variable_names"] == []
    assert morning["variables"] == {}
    assert morning["last_run"] is None
    hole = morning["latest_occurrence"]
    assert isinstance(hole, dict)
    assert hole["reason"] == "missed"

    paused = by_id[second.json()["id"]]
    assert paused["workflow_id"] == payroll
    assert paused["workflow_name"] == "Payroll"
    assert paused["state"] == "paused"
    assert paused["last_run"] is None
    assert paused["latest_occurrence"] is None

    scoped = list_all_schedules(account, workflow_id=payroll)
    assert scoped.status_code == 200, scoped.text
    scoped_ids = [row["id"] for row in scoped.json()["items"]]
    assert scoped_ids == [second.json()["id"]]

    reshaped = list_schedules(account, invoices).json()[0]
    assert reshaped["workflow_id"] == invoices
    assert reshaped["workflow_name"] == "Invoices"
    assert reshaped["last_run"] is None
    assert reshaped["latest_occurrence"]["reason"] == "missed"


def test_the_instance_list_pages_distinct_ids_in_order(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    seeded: list[str] = []
    for hour in range(5):
        created = create_schedule(
            account,
            workflow_id,
            cron=f"0 {hour} * * *",
            timezone="UTC",
            enabled=False,
        )
        assert created.status_code == 201, created.text
        seeded.append(created.json()["id"])

    found: list[str] = []
    cursor = None
    while True:
        response = list_all_schedules(
            account,
            limit=2,
            **({"cursor": cursor} if cursor else {}),
        )
        assert response.status_code == 200, response.text
        page = response.json()
        found.extend(item["id"] for item in page["items"])
        cursor = page.get("next_cursor")
        if cursor is None:
            break

    assert found == seeded
    assert len(found) == len(set(found)) == 5


def schedule_detail(account: Account, schedule_id: str):
    return account.client.get(f"/api/schedules/{schedule_id}")


def test_schedule_detail_interleaves_runs_and_holes_in_time_order(
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
    schedule_id = created.json()["id"]

    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE))
    tick()
    first_id = UUID(str(runs_of(account, workflow_id)[0]["id"]))
    with session_scope() as db:
        run = db.get(Run, first_id)
        assert run is not None
        run.status = RunStatus.SUCCEEDED
        run.ended_at = clock.now()
        db.commit()

    freeze(monkeypatch, datetime(2026, 8, 26, 9, 0, tzinfo=BELGRADE))
    tick()
    second_id = UUID(
        str(
            next(
                row["id"]
                for row in runs_of(account, workflow_id)
                if row["id"] != str(first_id)
            )
        )
    )
    with session_scope() as db:
        run = db.get(Run, second_id)
        assert run is not None
        run.status = RunStatus.RUNNING
        db.commit()

    freeze(monkeypatch, datetime(2026, 8, 27, 9, 0, tzinfo=BELGRADE))
    tick()

    detail = schedule_detail(account, schedule_id)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["schedule"]["id"] == schedule_id
    assert body["schedule"]["workflow_id"] == workflow_id
    history = body["history"]
    assert len(history) == 3
    assert {entry["kind"] for entry in history} == {"run", "occurrence"}
    ats = [datetime.fromisoformat(entry["at"]) for entry in history]
    assert ats == sorted(ats)
    runs = [entry for entry in history if entry["kind"] == "run"]
    holes = [entry for entry in history if entry["kind"] == "occurrence"]
    assert {entry["run_id"] for entry in runs} == {str(first_id), str(second_id)}
    by_run = {entry["run_id"]: entry for entry in runs}
    assert by_run[str(first_id)]["status"] == "succeeded"
    assert by_run[str(second_id)]["status"] == "running"
    assert len(holes) == 1
    assert holes[0]["reason"] == "overlap"
    assert holes[0]["blocking_run_id"] == str(second_id)
    assert datetime.fromisoformat(holes[0]["at"]).astimezone(BELGRADE) == datetime(
        2026, 8, 27, 9, 0, tzinfo=BELGRADE
    )
    last_run = body["last_run"]
    assert last_run["id"] == str(second_id)
    assert last_run["status"] == "running"
    assert last_run["ended_at"] is None
    assert len(body["next_occurrences"]) == 5


def run_now(account: Account, schedule_id: str):
    return account.client.post(f"/api/schedules/{schedule_id}/run-now")


def test_run_now_refuses_an_open_run_then_fires_after_it_ends(
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
    schedule_id = created.json()["id"]
    freeze(monkeypatch, datetime(2026, 8, 25, 9, 0, tzinfo=BELGRADE))
    tick()
    open_id = UUID(str(runs_of(account, workflow_id)[0]["id"]))
    with session_scope() as db:
        run = db.get(Run, open_id)
        assert run is not None
        run.status = RunStatus.RUNNING
        db.commit()

    refused = run_now(account, schedule_id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "schedule_run_active"
    assert refused.json()["blocking_run_id"] == str(open_id)

    with session_scope() as db:
        run = db.get(Run, open_id)
        assert run is not None
        run.status = RunStatus.SUCCEEDED
        run.ended_at = clock.now()
        db.commit()

    fired = run_now(account, schedule_id)
    assert fired.status_code == 201, fired.text
    run_id = fired.json()["run_id"]
    detail = schedule_detail(account, schedule_id)
    assert detail.status_code == 200, detail.text
    history_runs = [
        entry for entry in detail.json()["history"] if entry["kind"] == "run"
    ]
    assert {entry["run_id"] for entry in history_runs} == {
        str(open_id),
        run_id,
    }
    started = account.client.get(f"/api/runs/{run_id}")
    assert started.status_code == 200, started.text
    assert started.json()["run"]["trigger"] == "schedule"
    listed = list_all_schedules(account, workflow_id=workflow_id).json()["items"][0]
    assert listed["last_run"]["id"] == run_id
    assert listed["last_run"]["status"] == "queued"
    queued = [
        value.decode() if isinstance(value, bytes) else value
        for value in get_redis().lrange(DISPATCH_LIST, 0, -1)
    ]
    assert run_id in queued


def test_run_now_refuses_a_schedule_that_needs_values(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * *",
        timezone="Europe/Belgrade",
        enabled=True,
        variables={"city": "Belgrade"},
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]
    assert (
        save_draft(
            account,
            workflow_id,
            steps=[a_navigate_step(str(uuid4()))],
            variables=[{"name": "city"}, {"name": "region"}],
        ).status_code
        == 200
    )
    assert publish(account, workflow_id).status_code == 201
    listed = list_schedules(account, workflow_id).json()[0]
    assert listed["state"] == "needs_values"

    refused = run_now(account, schedule_id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "needs_values"
    assert refused.json()["variable_names"] == ["region"]
