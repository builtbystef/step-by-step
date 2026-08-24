"""The shell attention summary at its HTTP seam, against real Postgres."""

from datetime import timedelta
from typing import Any, cast
from uuid import UUID

import pytest
from conftest import Account
from sqlalchemy import text
from step_by_step_api import clock
from step_by_step_api.runs.models import Run, RunStatus
from step_by_step_api.runs.routes import attention_statement
from step_by_step_core.db import session_scope
from test_workflows import NewAccount, a_workflow

pytestmark = pytest.mark.integration


def seed_run(
    account: Account,
    workflow_id: str,
    status: RunStatus,
    *,
    deadline_offset: int | None = None,
) -> Run:
    run = Run(
        org_id=UUID(account.org_id),
        workflow_id=UUID(workflow_id),
        status=status,
        takeover_deadline_at=(
            clock.now() + timedelta(seconds=deadline_offset)
            if deadline_offset is not None
            else None
        ),
        variables={},
    )
    return run


def test_attention_caps_and_orders_waiting_runs_and_isolates_organizations(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()
    workflow_id = a_workflow(owner, "Invoice download — AcmeBank")
    deadlines = [70, 10, 60, 20, 50, 30, 40]
    with session_scope() as db:
        waiting_by_offset = [
            (
                offset,
                seed_run(
                    owner,
                    workflow_id,
                    RunStatus.WAITING_FOR_HUMAN,
                    deadline_offset=offset,
                ),
            )
            for offset in deadlines
        ]
        waiting = [run for _, run in waiting_by_offset]
        db.add_all(
            [
                *waiting,
                seed_run(owner, workflow_id, RunStatus.RUNNING),
                seed_run(owner, workflow_id, RunStatus.QUEUED),
            ]
        )
        db.commit()
        ordered_ids = [
            str(run.id)
            for _, run in sorted(waiting_by_offset, key=lambda item: item[0])[:5]
        ]

    response = owner.client.get("/api/attention")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["run_id"] for item in payload["waiting"]] == ordered_ids
    assert [item["workflow_name"] for item in payload["waiting"]] == [
        "Invoice download — AcmeBank"
    ] * 5
    assert payload["waiting_count"] == 7
    assert payload["running_count"] == 1
    assert payload["queued_count"] == 1

    invisible = stranger.client.get("/api/attention")
    assert invisible.status_code == 200, invisible.text
    assert invisible.json() == {
        "waiting": [],
        "waiting_count": 0,
        "running_count": 0,
        "queued_count": 0,
    }


def test_attention_plan_touches_only_the_three_non_terminal_runs(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    with session_scope() as db:
        db.execute(
            text(
                """
                INSERT INTO runs (
                  id, org_id, workflow_id, is_test, trigger, status, variables,
                  timeout_ms, auto_handback_disabled, automation_ms
                )
                SELECT gen_random_uuid(), :org_id, :workflow_id, false, 'manual',
                       'succeeded', '{}'::jsonb, 1800000, false, 0
                FROM generate_series(1, 50000)
                """
            ),
            {"org_id": account.org_id, "workflow_id": workflow_id},
        )
        db.add_all(
            [
                seed_run(account, workflow_id, RunStatus.QUEUED),
                seed_run(account, workflow_id, RunStatus.RUNNING),
                seed_run(
                    account,
                    workflow_id,
                    RunStatus.WAITING_FOR_HUMAN,
                    deadline_offset=60,
                ),
            ]
        )
        db.commit()
        db.execute(text("ANALYZE runs"))
        statement = attention_statement(UUID(account.org_id)).compile(
            db.get_bind(), compile_kwargs={"literal_binds": True}
        )
        explained = db.execute(
            text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {statement}")
        ).scalar_one()
        plan = cast(dict[str, Any], explained[0]["Plan"])

    index_nodes = [
        node
        for node in walk_plan(plan)
        if node.get("Index Name") == "ix_runs_org_takeover_attention"
    ]
    assert len(index_nodes) == 1
    assert index_nodes[0]["Actual Rows"] == 3


def walk_plan(plan: dict[str, Any]):
    yield plan
    for child in cast(list[dict[str, Any]], plan.get("Plans", [])):
        yield from walk_plan(child)
