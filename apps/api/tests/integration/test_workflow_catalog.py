import json
from base64 import urlsafe_b64encode
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from conftest import Account
from sqlalchemy import func, select
from step_by_step_api.batches.models import Batch
from step_by_step_api.runs.models import (
    Artifact,
    Run,
    RunStatus,
    StepResult,
    StepResultStatus,
)
from step_by_step_api.schedules.models import Schedule
from step_by_step_core.db import session_scope
from step_by_step_core.objects import artifact_bucket, object_store
from test_batches import create_batch
from test_run_artifacts import object_missing, seed_artifact
from test_runs import published_workflow, start
from test_schedules import create_schedule
from test_workflows import (
    a_click_step,
    a_navigate_step,
    a_workflow,
    read_draft,
    save_draft,
)

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


def test_the_list_answers_a_summary_of_every_workflow_the_organization_owns(
    new_account: NewAccount,
) -> None:
    account = new_account()
    a_workflow(account, name="Invoices")
    a_workflow(account, name="Payroll")

    listed = account.client.get("/api/workflows")

    assert listed.status_code == 200, listed.text
    names = {row["name"] for row in listed.json()["items"]}
    assert names == {"Invoices", "Payroll"}


def test_a_row_says_what_it_is_before_it_is_opened(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")

    never_published = one_row(account, workflow_id)

    assert never_published["draft_state"] == "never-published"
    assert "published_version" not in never_published
    assert never_published["created_at"] <= never_published["last_activity_at"]

    assert (
        save_draft(
            account, workflow_id, steps=[a_navigate_step(str(uuid4()))]
        ).status_code
        == 200
    )
    assert (
        account.client.post(f"/api/workflows/{workflow_id}/versions").status_code == 201
    )

    published = one_row(account, workflow_id)

    assert published["draft_state"] == "in-sync"
    assert published["published_version"] == 1


def one_row(account: Account, workflow_id: str) -> dict[str, Any]:
    listed = account.client.get("/api/workflows")
    assert listed.status_code == 200, listed.text
    rows: list[dict[str, Any]] = [
        row for row in listed.json()["items"] if row["id"] == workflow_id
    ]
    assert len(rows) == 1, rows
    return rows[0]


def listed_names(account: Account, **query: object) -> list[str]:
    listed = account.client.get("/api/workflows", params=query)
    assert listed.status_code == 200, listed.text
    return [row["name"] for row in listed.json()["items"]]


def test_another_organizations_workflows_are_not_in_the_list(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    a_workflow(account, name="Invoices")

    assert listed_names(stranger) == []


def test_the_search_matches_a_name_case_insensitively(new_account: NewAccount) -> None:
    account = new_account()
    for name in ("ACME payroll", "Acme invoices", "Northwind orders"):
        a_workflow(account, name=name)

    assert sorted(listed_names(account, q="acme")) == ["ACME payroll", "Acme invoices"]
    assert listed_names(account, q="northwind") == ["Northwind orders"]


def test_the_search_reads_a_wildcard_as_a_character_to_look_for(
    new_account: NewAccount,
) -> None:
    account = new_account()
    a_workflow(account, name="Discount 50%")
    a_workflow(account, name="Payroll")

    assert listed_names(account, q="50%") == ["Discount 50%"]
    assert listed_names(account, q="%") == ["Discount 50%"]


def test_the_list_sorts_by_activity_until_it_is_told_otherwise(
    new_account: NewAccount,
) -> None:
    account = new_account()
    older = a_workflow(account, name="Zebra")
    a_workflow(account, name="Yak")

    assert listed_names(account) == ["Yak", "Zebra"]

    assert (
        save_draft(account, older, steps=[a_navigate_step(str(uuid4()))]).status_code
        == 200
    )

    assert listed_names(account) == ["Zebra", "Yak"]


def test_the_list_sorts_by_name_and_by_creation_when_asked(
    new_account: NewAccount,
) -> None:
    account = new_account()
    for name in ("Payroll", "Acme", "Northwind"):
        a_workflow(account, name=name)

    assert listed_names(account, sort="name") == ["Acme", "Northwind", "Payroll"]
    assert listed_names(account, sort="created") == ["Northwind", "Acme", "Payroll"]


def test_a_sort_the_list_does_not_have_is_refused(new_account: NewAccount) -> None:
    account = new_account()

    refused = account.client.get("/api/workflows", params={"sort": "colour"})

    assert refused.status_code == 422, refused.text


def test_paging_to_exhaustion_yields_every_workflow_once_and_in_order(
    new_account: NewAccount,
) -> None:
    account = new_account()
    ids = {
        name: a_workflow(account, name=name)
        for name in (f"Workflow {number:02d}" for number in range(25))
    }
    moved = ids["Workflow 07"]

    seen: list[dict[str, object]] = []
    cursor: str | None = None
    while True:
        page = account.client.get(
            "/api/workflows",
            params={
                "sort": "name",
                "limit": 10,
                **({"cursor": cursor} if cursor else {}),
            },
        )
        assert page.status_code == 200, page.text
        body = page.json()
        assert len(body["items"]) <= 10
        seen += body["items"]
        assert (
            save_draft(
                account, moved, steps=[a_navigate_step(str(uuid4()))]
            ).status_code
            == 200
        )
        cursor = body.get("next_cursor")
        if cursor is None:
            break

    assert len({row["id"] for row in seen}) == 25
    assert [row["name"] for row in seen] == sorted(ids)


def test_a_cursor_that_did_not_come_from_this_list_is_refused(
    new_account: NewAccount,
) -> None:
    account = new_account()
    a_workflow(account)

    refused = account.client.get("/api/workflows", params={"cursor": "not-a-cursor"})

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "bad_cursor"


def test_a_cursor_is_refused_by_the_order_it_was_not_cut_from(
    new_account: NewAccount,
) -> None:
    account = new_account()
    for name in ("Acme", "Northwind"):
        a_workflow(account, name=name)

    first = account.client.get("/api/workflows", params={"sort": "name", "limit": 1})
    cursor = first.json()["next_cursor"]

    refused = account.client.get(
        "/api/workflows", params={"sort": "created", "cursor": cursor}
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "bad_cursor"


def test_a_tampered_cursor_is_refused_rather_than_crashed_on(
    new_account: NewAccount,
) -> None:
    account = new_account()
    a_workflow(account)
    tampered = urlsafe_b64encode(
        json.dumps(
            {"s": "activity", "k": "the beginning of time", "i": str(uuid4())}
        ).encode()
    ).decode()

    refused = account.client.get("/api/workflows", params={"cursor": tampered})

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "bad_cursor"


def test_renaming_a_workflow_changes_what_the_list_calls_it(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")

    renamed = account.client.patch(
        f"/api/workflows/{workflow_id}", json={"name": "Invoices, monthly"}
    )

    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Invoices, monthly"
    assert listed_names(account) == ["Invoices, monthly"]


def test_another_organizations_workflow_cannot_be_renamed(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.patch(
        f"/api/workflows/{workflow_id}", json={"name": "Mine now"}
    )

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"


def test_a_duplicate_carries_the_steps_across_under_fresh_ids(
    new_account: NewAccount,
) -> None:
    account = new_account()
    source = a_workflow(account, name="Invoices")
    steps = [a_navigate_step(str(uuid4())), a_click_step(str(uuid4()))]
    assert (
        save_draft(
            account, source, steps=steps, variables=[{"name": "month"}]
        ).status_code
        == 200
    )

    copied = account.client.post(f"/api/workflows/{source}/duplicate")

    assert copied.status_code == 201, copied.text
    original = read_draft(account, source).json()
    copy = read_draft(account, copied.json()["id"]).json()
    assert [step["id"] for step in copy["steps"]] != [step["id"] for step in steps]
    assert [step["type"] for step in copy["steps"]] == ["navigate", "click"]
    assert [without_id(step) for step in copy["steps"]] == [
        without_id(step) for step in original["steps"]
    ]
    assert copy["variables"] == original["variables"] == [{"name": "month"}]


def without_id(step: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in step.items() if key != "id"}


def test_a_duplicate_of_a_published_workflow_has_published_nothing(
    new_account: NewAccount,
) -> None:
    account = new_account()
    source = a_workflow(account, name="Invoices")
    assert save_draft(account, source).status_code == 200
    assert account.client.post(f"/api/workflows/{source}/versions").status_code == 201

    copied = account.client.post(f"/api/workflows/{source}/duplicate")

    assert copied.status_code == 201, copied.text
    row = one_row(account, copied.json()["id"])
    assert row["draft_state"] == "never-published"
    assert "published_version" not in row
    assert row["name"] != "Invoices"
    assert (
        account.client.get(f"/api/workflows/{copied.json()['id']}/versions").json()
        == []
    )


def test_another_organizations_workflow_cannot_be_duplicated(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.post(f"/api/workflows/{workflow_id}/duplicate")

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"


def test_deleting_a_workflow_takes_its_draft_and_its_versions_with_it(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")
    assert save_draft(account, workflow_id).status_code == 200
    assert (
        account.client.post(f"/api/workflows/{workflow_id}/versions").status_code == 201
    )
    kept = a_workflow(account, name="Payroll")

    deleted = account.client.delete(f"/api/workflows/{workflow_id}")

    assert deleted.status_code == 204, deleted.text
    assert read_draft(account, workflow_id).status_code == 404
    assert (
        account.client.get(f"/api/workflows/{workflow_id}/versions").status_code == 404
    )
    assert (
        account.client.get(f"/api/workflows/{workflow_id}/versions/1").status_code
        == 404
    )
    assert [row["id"] for row in listed_rows(account)] == [kept]


def listed_rows(account: Account, **query: object) -> list[dict[str, Any]]:
    listed = account.client.get("/api/workflows", params=query)
    assert listed.status_code == 200, listed.text
    items: list[dict[str, Any]] = listed.json()["items"]
    return items


def test_another_organizations_workflow_cannot_be_deleted(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.delete(f"/api/workflows/{workflow_id}")

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"
    assert len(listed_rows(account)) == 1


def test_one_workflow_reads_back_as_the_row_the_list_would_draw(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")
    assert save_draft(account, workflow_id).status_code == 200
    assert (
        account.client.post(f"/api/workflows/{workflow_id}/versions").status_code == 201
    )

    read = account.client.get(f"/api/workflows/{workflow_id}")

    assert read.status_code == 200, read.text
    assert read.json() == one_row(account, workflow_id)


def test_another_organizations_workflow_cannot_be_read(new_account: NewAccount) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.get(f"/api/workflows/{workflow_id}")

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"


def test_a_workflow_says_what_a_step_timeout_falls_back_to(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)

    read = account.client.get(f"/api/workflows/{workflow_id}")

    assert read.status_code == 200, read.text
    assert read.json()["default_step_timeout_ms"] == 30_000


def finish(
    run_id: str, *, status: RunStatus = RunStatus.SUCCEEDED, duration_ms: int = 1_000
) -> None:
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = status
        run.started_at = run.queued_at
        run.ended_at = run.queued_at + timedelta(milliseconds=duration_ms)
        db.commit()


def test_a_row_carries_the_last_run(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    first = start(account, workflow_id, variables={}).json()["run_id"]
    finish(first, duration_ms=4_000)
    second = start(account, workflow_id, variables={}).json()["run_id"]

    row = one_row(account, workflow_id)

    assert row["last_run"]["id"] == second
    assert row["last_run"]["status"] == "queued"
    assert "finished_at" not in row["last_run"]

    finish(second, duration_ms=2_000)
    done = one_row(account, workflow_id)
    assert done["last_run"]["id"] == second
    assert done["last_run"]["status"] == "succeeded"
    assert done["last_run"]["finished_at"] is not None


def test_a_never_run_row_omits_last_run(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = a_workflow(account)

    row = one_row(account, workflow_id)

    assert "last_run" not in row


def test_a_row_carries_the_schedule_count_and_a_single_schedule_label(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)

    empty = one_row(account, workflow_id)
    assert empty["schedule_count"] == 0
    assert "schedule_label" not in empty

    created = create_schedule(
        account,
        workflow_id,
        cron="0 9 * * 1-5",
        timezone="Europe/Belgrade",
        enabled=True,
    )
    assert created.status_code == 201, created.text

    one = one_row(account, workflow_id)
    assert one["schedule_count"] == 1
    assert one["schedule_label"] == "weekdays 09:00"

    for hour in ("10", "11"):
        assert (
            create_schedule(
                account,
                workflow_id,
                cron=f"0 {hour} * * 1-5",
                timezone="Europe/Belgrade",
                enabled=True,
            ).status_code
            == 201
        )

    many = one_row(account, workflow_id)
    assert many["schedule_count"] == 3
    assert "schedule_label" not in many


def test_a_row_carries_the_recent_run_median_once_three_have_succeeded(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    for duration in (1_000, 3_000):
        finish(
            start(account, workflow_id, variables={}).json()["run_id"],
            duration_ms=duration,
        )

    too_few = one_row(account, workflow_id)
    assert "recent_run_median_ms" not in too_few

    finish(
        start(account, workflow_id, variables={}).json()["run_id"],
        duration_ms=5_000,
    )

    row = one_row(account, workflow_id)
    assert row["recent_run_median_ms"] == 3_000


def test_activity_sort_follows_the_latest_run_then_falls_back_to_the_workflow(
    new_account: NewAccount,
) -> None:
    account = new_account()
    older = published_workflow(account)
    newer = published_workflow(account)

    assert listed_rows(account)[0]["id"] == newer

    start(account, older, variables={})

    ordered = listed_rows(account)
    assert [row["id"] for row in ordered] == [older, newer]
    assert ordered[0]["last_activity_at"] >= ordered[1]["last_activity_at"]


def test_deleting_while_a_run_is_live_is_conflict_then_succeeds_once_it_ends(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    run_id = start(account, workflow_id, variables={}).json()["run_id"]

    refused = account.client.delete(f"/api/workflows/{workflow_id}")

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "run_active"
    assert one_row(account, workflow_id)["id"] == workflow_id

    finish(run_id)
    deleted = account.client.delete(f"/api/workflows/{workflow_id}")
    assert deleted.status_code == 204, deleted.text
    assert account.client.get(f"/api/workflows/{workflow_id}").status_code == 404


def test_deleting_a_workflow_takes_schedules_batches_runs_results_and_artifacts(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account, variables=[{"name": "city"}])
    for hour in ("9", "10"):
        assert (
            create_schedule(
                account,
                workflow_id,
                cron=f"0 {hour} * * 1-5",
                timezone="Europe/Belgrade",
                enabled=True,
                variables={"city": "Oslo"},
            ).status_code
            == 201
        )
    batch = create_batch(
        account,
        workflow_id,
        name="Monthly",
        rows=[{"variables": {}}],
    )
    assert batch.status_code == 201, batch.text
    batch_id = batch.json()["batch_id"]
    run_ids: list[str] = []
    for _ in range(42):
        created = start(account, workflow_id, variables={"city": "Oslo"})
        assert created.status_code == 201, created.text
        run_id = created.json()["run_id"]
        finish(run_id)
        run_ids.append(run_id)
    last = UUID(run_ids[-1])
    with session_scope() as db:
        db.add(
            StepResult(
                run_id=last,
                step_id=uuid4(),
                position=0,
                status=StepResultStatus.PASSED,
            )
        )
        db.commit()
    keys: list[str] = []
    object_store.cache_clear()
    try:
        artifact = seed_artifact(last, keys)
        before = one_row(account, workflow_id)
        assert before["schedule_count"] == 2
        assert before["run_count"] == 42

        deleted = account.client.delete(f"/api/workflows/{workflow_id}")

        assert deleted.status_code == 204, deleted.text
        assert account.client.get(f"/api/workflows/{workflow_id}").status_code == 404
        assert (
            account.client.get("/api/runs", params={"workflow_id": workflow_id}).json()[
                "items"
            ]
            == []
        )
        with session_scope() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(Schedule)
                    .where(Schedule.workflow_id == UUID(workflow_id))
                )
                == 0
            )
            assert db.get(Batch, UUID(batch_id)) is None
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(Run)
                    .where(Run.workflow_id == UUID(workflow_id))
                )
                == 0
            )
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(StepResult)
                    .where(StepResult.run_id == last)
                )
                == 0
            )
            assert db.get(Artifact, artifact.id) is None
        assert object_missing(artifact.object_key)
    finally:
        for key in keys:
            object_store().delete_object(Bucket=artifact_bucket(), Key=key)
        object_store.cache_clear()
