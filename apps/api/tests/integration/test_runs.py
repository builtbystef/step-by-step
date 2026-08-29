"""The Run store and dispatch surface: HTTP against Postgres and Redis."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from conftest import Account
from step_by_step_api import clock
from step_by_step_api.runs.models import (
    Run,
    RunControlInterval,
    RunControlKind,
    RunStatus,
    StepResult,
    StepResultStatus,
)
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from step_by_step_worker.store import PostgresRunStore
from test_secrets import create
from test_workflow_versions import publish
from test_workflows import NewAccount, a_navigate_step, a_workflow, save_draft

pytestmark = pytest.mark.integration
DISPATCH_LIST = "runs:dispatch"


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


def start(account: Account, workflow_id: str, **body: object):
    return account.client.post(f"/api/workflows/{workflow_id}/runs", json=body)


def detail(account: Account, run_id: str):
    return account.client.get(f"/api/runs/{run_id}")


def published_workflow(
    account: Account, *, variables: list[dict[str, object]] | None = None
) -> str:
    workflow_id = a_workflow(account)
    saved = save_draft(
        account,
        workflow_id,
        steps=[a_navigate_step(str(uuid4()))],
        variables=variables or [],
    )
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201
    return workflow_id


def test_starting_a_run_persists_it_and_dispatches_its_id_once(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)

    created = start(account, workflow_id, variables={})

    assert created.status_code == 201, created.text
    run_id = created.json()["run_id"]
    assert detail(account, run_id).json()["run"]["status"] == "queued"
    queued = [
        value.decode() if isinstance(value, bytes) else value
        for value in get_redis().lrange(DISPATCH_LIST, 0, -1)
    ]
    assert queued == [run_id]


def test_test_and_manual_runs_store_the_document_they_execute(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    changed = [a_navigate_step(str(uuid4()))]
    assert save_draft(account, workflow_id, steps=changed).status_code == 200

    manual_id = start(account, workflow_id, variables={}).json()["run_id"]
    test_id = start(account, workflow_id, variables={}, test=True).json()["run_id"]
    manual = detail(account, manual_id).json()["run"]
    test = detail(account, test_id).json()["run"]

    assert manual["trigger"] == "manual"
    assert manual["version_number"] == 1
    assert manual["draft_snapshot"] is None
    assert test["trigger"] == "test"
    assert test["version_number"] is None
    assert test["draft_snapshot"]["steps"] == changed


def test_worker_claim_is_conditional_and_selects_the_test_run_snapshot(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    draft_step_id = uuid4()
    changed = [a_navigate_step(str(draft_step_id))]
    assert save_draft(account, workflow_id, steps=changed).status_code == 200
    manual_id = start(account, workflow_id, variables={}).json()["run_id"]
    test_id = start(account, workflow_id, variables={}, test=True).json()["run_id"]
    cancelled_id = start(account, workflow_id, variables={}).json()["run_id"]
    assert account.client.post(f"/api/runs/{cancelled_id}/cancel").status_code == 202
    store = PostgresRunStore()

    manual = store.claim(UUID(manual_id), "worker-1", "worker-1:5900", clock.now())
    assert manual is not None
    assert (
        store.claim(UUID(manual_id), "worker-2", "worker-2:5900", clock.now()) is None
    )
    assert (
        store.claim(UUID(cancelled_id), "worker-1", "worker-1:5900", clock.now())
        is None
    )
    snapshot = store.claim(UUID(test_id), "worker-1", "worker-1:5900", clock.now())

    assert snapshot is not None
    assert [step.id for step in snapshot.document.steps] == [draft_step_id]
    claimed = detail(account, manual_id).json()["run"]
    assert claimed["status"] == "running"
    assert claimed["worker_id"] == "worker-1"
    assert claimed["worker_vnc_endpoint"] == "worker-1:5900"
    assert claimed["started_at"] is not None
    assert claimed["heartbeat_at"] is not None


def test_secret_variable_values_never_enter_a_run(new_account: NewAccount) -> None:
    account = new_account()
    secret = create(account).json()
    workflow_id = a_workflow(account)
    saved = save_draft(
        account,
        workflow_id,
        steps=[a_navigate_step(str(uuid4()))],
        variables=[
            {"name": "customer"},
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

    created = start(
        account,
        workflow_id,
        variables={"customer": "Ada", "password": "do-not-store"},
    )

    assert created.status_code == 201, created.text
    stored = detail(account, created.json()["run_id"]).json()["run"]["variables"]
    assert stored == {"customer": "Ada"}


def test_run_summaries_carry_non_secret_variables(
    new_account: NewAccount,
) -> None:
    """GET /api/runs items expose the value set "fill from my last Run" reads."""
    account = new_account()
    secret = create(account).json()
    workflow_id = a_workflow(account)
    saved = save_draft(
        account,
        workflow_id,
        steps=[a_navigate_step(str(uuid4()))],
        variables=[
            {"name": "customer"},
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
    created = start(
        account,
        workflow_id,
        variables={"customer": "Ada", "password": "do-not-store"},
    )
    assert created.status_code == 201, created.text

    listed = account.client.get("/api/runs", params={"workflow_id": workflow_id})

    assert listed.status_code == 200, listed.text
    item = listed.json()["items"][0]
    assert item["id"] == created.json()["run_id"]
    assert item["variables"] == {"customer": "Ada"}
    assert "password" not in item["variables"]


def test_cancelling_a_queued_run_is_immediate(new_account: NewAccount) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]

    cancelled = account.client.post(f"/api/runs/{run_id}/cancel")

    assert cancelled.status_code == 202
    assert detail(account, run_id).json()["run"]["status"] == "cancelled"


def test_runs_filter_and_page_by_a_stable_keyset(new_account: NewAccount) -> None:
    account = new_account()
    wanted = published_workflow(account)
    other = published_workflow(account)
    seeded: list[UUID] = []
    with session_scope() as db:
        for index in range(25):
            run = Run(
                org_id=UUID(account.org_id),
                workflow_id=UUID(wanted),
                status=RunStatus.FAILED,
                queued_at=clock.now() + timedelta(seconds=index),
                variables={},
            )
            db.add(run)
            db.flush()
            seeded.append(run.id)
        db.add(
            Run(
                org_id=UUID(account.org_id),
                workflow_id=UUID(other),
                status=RunStatus.FAILED,
                variables={},
            )
        )
        db.add(
            Run(
                org_id=UUID(account.org_id),
                workflow_id=UUID(wanted),
                status=RunStatus.SUCCEEDED,
                variables={},
            )
        )
        db.commit()

    found: list[str] = []
    cursor = None
    while True:
        response = account.client.get(
            "/api/runs",
            params={
                "workflow_id": wanted,
                "status": "failed",
                "limit": 10,
                **({"cursor": cursor} if cursor else {}),
            },
        )
        assert response.status_code == 200, response.text
        page = response.json()
        found.extend(item["id"] for item in page["items"])
        cursor = page.get("next_cursor")
        if cursor is None:
            break

    assert found == [str(run_id) for run_id in reversed(seeded)]
    assert len(found) == len(set(found)) == 25


def test_list_carries_the_workflow_name_the_runs_list_renders(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    run_id = start(account, workflow_id, variables={}).json()["run_id"]

    listed = account.client.get("/api/runs")

    assert listed.status_code == 200, listed.text
    item = listed.json()["items"][0]
    assert item["id"] == run_id
    assert item["workflow_id"] == workflow_id
    assert item["workflow_name"] == "Invoices"


def test_list_filters_by_trigger(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    manual_id = start(account, workflow_id, variables={}).json()["run_id"]
    test_id = start(account, workflow_id, variables={}, test=True).json()["run_id"]

    manuals = account.client.get("/api/runs", params={"trigger": "manual"})
    tests = account.client.get("/api/runs", params={"trigger": "test"})

    assert [item["id"] for item in manuals.json()["items"]] == [manual_id]
    assert [item["id"] for item in tests.json()["items"]] == [test_id]


def test_detail_orders_results_and_carries_the_run_timeline_and_artifacts(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    with session_scope() as db:
        db.add_all(
            [
                StepResult(
                    run_id=UUID(run_id),
                    step_id=uuid4(),
                    position=2,
                    status=StepResultStatus.SKIPPED,
                ),
                StepResult(
                    run_id=UUID(run_id),
                    step_id=uuid4(),
                    position=1,
                    status=StepResultStatus.PASSED,
                ),
                RunControlInterval(
                    run_id=UUID(run_id),
                    kind=RunControlKind.AUTOMATION,
                    started_at=clock.now(),
                ),
            ]
        )
        db.commit()

    payload = detail(account, run_id).json()

    assert payload["run"]["id"] == run_id
    assert [result["position"] for result in payload["step_results"]] == [1, 2]
    assert [interval["kind"] for interval in payload["control_intervals"]] == [
        "automation"
    ]
    assert payload["artifacts"] == []
    assert payload["batch_row"] is None


def test_every_run_route_hides_another_organizations_run(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()
    workflow_id = published_workflow(owner)
    run_id = start(owner, workflow_id, variables={}).json()["run_id"]

    assert start(stranger, workflow_id, variables={}).status_code == 404
    assert detail(stranger, run_id).status_code == 404
    assert stranger.client.post(f"/api/runs/{run_id}/cancel").status_code == 404
    assert stranger.client.delete(f"/api/runs/{run_id}").status_code == 404
    assert (
        stranger.client.get(
            f"/api/runs/{run_id}/artifacts/{uuid4()}/download",
            follow_redirects=False,
        ).status_code
        == 404
    )


def test_a_normal_run_requires_a_published_version_but_a_test_run_does_not(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)

    refused = start(account, workflow_id, variables={})
    accepted = start(account, workflow_id, variables={}, test=True)

    assert refused.status_code == 409
    assert refused.json()["code"] == "no_published_version"
    assert accepted.status_code == 201


def test_a_test_run_freezes_the_draft_and_mints_no_version(
    new_account: NewAccount,
) -> None:
    """Draft edits after start do not affect the Run; the Version list is untouched."""
    account = new_account()
    workflow_id = a_workflow(account)
    first = [a_navigate_step(str(uuid4()))]
    assert save_draft(account, workflow_id, steps=first).status_code == 200
    assert account.client.get(f"/api/workflows/{workflow_id}/versions").json() == []

    created = start(account, workflow_id, variables={}, test=True)
    assert created.status_code == 201, created.text
    run_id = created.json()["run_id"]
    later = [a_navigate_step(str(uuid4()))]
    assert save_draft(account, workflow_id, steps=later).status_code == 200

    run = detail(account, run_id).json()["run"]
    assert run["is_test"] is True
    assert run["draft_snapshot"]["steps"] == first
    assert run["version_number"] is None
    assert account.client.get(f"/api/workflows/{workflow_id}/versions").json() == []


def test_selector_drift_flags_steps_that_matched_below_the_recorded_best(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_workflow(account)
    stable = uuid4()
    moved = uuid4()
    run_id = start(account, workflow_id, variables={}).json()["run_id"]
    with session_scope() as db:
        db.add_all(
            [
                StepResult(
                    run_id=UUID(run_id),
                    step_id=stable,
                    position=0,
                    status=StepResultStatus.PASSED,
                    matched_candidate_rank=0,
                ),
                StepResult(
                    run_id=UUID(run_id),
                    step_id=moved,
                    position=1,
                    status=StepResultStatus.PASSED,
                    matched_candidate_rank=2,
                ),
            ]
        )
        db.commit()

    drifted = account.client.get(f"/api/workflows/{workflow_id}/selector-drift")

    assert drifted.status_code == 200, drifted.text
    assert drifted.json()["drifted_step_ids"] == [str(moved)]


def test_selector_drift_only_reads_the_most_recent_runs(
    new_account: NewAccount,
) -> None:
    """Eleven Runs: only the ten newest count, matching the catalog's recent window."""
    account = new_account()
    workflow_id = published_workflow(account)
    stale = uuid4()
    fresh = uuid4()
    with session_scope() as db:
        for index in range(11):
            run = Run(
                org_id=UUID(account.org_id),
                workflow_id=UUID(workflow_id),
                status=RunStatus.SUCCEEDED,
                queued_at=clock.now() + timedelta(seconds=index),
                variables={},
            )
            db.add(run)
            db.flush()
            db.add(
                StepResult(
                    run_id=run.id,
                    step_id=stale if index == 0 else fresh,
                    position=0,
                    status=StepResultStatus.PASSED,
                    matched_candidate_rank=2 if index == 0 else 0,
                )
            )
        db.commit()

    drifted = account.client.get(f"/api/workflows/{workflow_id}/selector-drift")

    assert drifted.status_code == 200, drifted.text
    assert drifted.json()["drifted_step_ids"] == []


def test_selector_drift_hides_another_organizations_workflow(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()
    workflow_id = published_workflow(owner)

    assert (
        stranger.client.get(f"/api/workflows/{workflow_id}/selector-drift").status_code
        == 404
    )
