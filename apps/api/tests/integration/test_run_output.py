"""Run output: assembled on read from Step Results, as JSON or CSV."""

import csv
import io
import json
from uuid import UUID, uuid4

import pytest
from conftest import Account, join
from step_by_step_api.runs.models import (
    FailureReason,
    Run,
    RunStatus,
    StepResult,
    StepResultStatus,
)
from step_by_step_core.db import session_scope
from test_runs import start
from test_workflow_versions import publish
from test_workflows import NewAccount, a_navigate_step, a_target, a_workflow, save_draft

pytestmark = pytest.mark.integration


def run_output(account: Account, run_id: str, **params: object):
    return account.client.get(f"/api/runs/{run_id}/output", params=params)


def a_list_extract(step_id: str, name: str, fields: list[str]) -> dict[str, object]:
    return {
        "id": step_id,
        "type": "extract",
        "label": f"Read {name}",
        "payload": {
            "target": a_target(),
            "outputName": name,
            "mode": "list",
            "fields": [{"name": field, "subSelector": f".{field}"} for field in fields],
        },
    }


def a_scalar_extract(step_id: str, name: str) -> dict[str, object]:
    return {
        "id": step_id,
        "type": "extract",
        "label": f"Read {name}",
        "payload": {
            "target": a_target(),
            "outputName": name,
            "mode": "scalar",
        },
    }


def published(account: Account, steps: list[dict[str, object]]) -> str:
    workflow_id = a_workflow(account)
    saved = save_draft(account, workflow_id, steps=steps)
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201
    return workflow_id


def fail_run(run_id: str) -> None:
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = RunStatus.FAILED
        run.failure_reason = FailureReason.STEP_FAILED
        db.commit()


def records(count: int) -> list[dict[str, str]]:
    return [
        {
            "number": f"INV-{index:04d}",
            "client": f"Client {index}",
            "amount": f"{index}.00",
            "status": "open",
        }
        for index in range(count)
    ]


def add_extract(run_id: str, step_id: str, position: int, value: object) -> None:
    with session_scope() as db:
        db.add(
            StepResult(
                run_id=UUID(run_id),
                step_id=UUID(step_id),
                position=position,
                status=StepResultStatus.PASSED,
                extracted_value=value,
            )
        )
        db.commit()


def test_list_mode_extract_is_the_records_in_both_formats(
    new_account: NewAccount,
) -> None:
    account = new_account()
    extract_id = str(uuid4())
    workflow_id = published(
        account,
        [
            a_navigate_step(str(uuid4())),
            a_list_extract(
                extract_id, "invoices", ["number", "client", "amount", "status"]
            ),
        ],
    )
    run_id = start(account, workflow_id, variables={}).json()["run_id"]
    extracted = records(24)
    add_extract(run_id, extract_id, 1, extracted)

    as_json = run_output(account, run_id, format="json")
    assert as_json.status_code == 200, as_json.text
    assert as_json.json() == extracted

    as_csv = run_output(account, run_id, format="csv")
    assert as_csv.status_code == 200, as_csv.text
    assert "text/csv" in as_csv.headers["content-type"]
    parsed = list(csv.reader(io.StringIO(as_csv.text)))
    assert parsed[0] == ["number", "client", "amount", "status"]
    assert parsed[1:] == [
        [row["number"], row["client"], row["amount"], row["status"]]
        for row in extracted
    ]
    assert len(parsed[1:]) == 24


def test_two_extract_steps_combine_under_their_output_names(
    new_account: NewAccount,
) -> None:
    account = new_account()
    invoices_id = str(uuid4())
    total_id = str(uuid4())
    workflow_id = published(
        account,
        [
            a_list_extract(invoices_id, "invoices", ["number", "client"]),
            a_scalar_extract(total_id, "total"),
        ],
    )
    run_id = start(account, workflow_id, variables={}).json()["run_id"]
    invoices = records(2)
    add_extract(run_id, invoices_id, 0, invoices)
    add_extract(run_id, total_id, 1, "48.00")

    as_json = run_output(account, run_id, format="json")
    assert as_json.status_code == 200, as_json.text
    assert as_json.json() == {"invoices": invoices, "total": "48.00"}

    as_csv = run_output(account, run_id, format="csv")
    assert as_csv.status_code == 200, as_csv.text
    parsed = list(csv.reader(io.StringIO(as_csv.text)))
    assert parsed[0] == ["invoices", "total"]
    assert json.loads(parsed[1][0]) == invoices
    assert parsed[1][1] == "48.00"


def test_no_extract_steps_is_empty(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = published(account, [a_navigate_step(str(uuid4()))])
    run_id = start(account, workflow_id, variables={}).json()["run_id"]

    as_json = run_output(account, run_id, format="json")
    assert as_json.status_code == 200, as_json.text
    assert as_json.json() == {}

    as_csv = run_output(account, run_id, format="csv")
    assert as_csv.status_code == 200, as_csv.text
    assert as_csv.text == ""


def test_failed_run_keeps_what_was_extracted_before_the_failure(
    new_account: NewAccount,
) -> None:
    account = new_account()
    extract_id = str(uuid4())
    workflow_id = published(
        account,
        [
            a_list_extract(
                extract_id, "invoices", ["number", "client", "amount", "status"]
            ),
            a_navigate_step(str(uuid4())),
        ],
    )
    run_id = start(account, workflow_id, variables={}).json()["run_id"]
    extracted = records(3)
    add_extract(run_id, extract_id, 0, extracted)
    fail_run(run_id)

    as_json = run_output(account, run_id, format="json")
    assert as_json.status_code == 200, as_json.text
    assert as_json.json() == extracted


def test_another_organizations_run_is_404(new_account: NewAccount) -> None:
    owner = new_account()
    stranger = new_account()
    workflow_id = published(owner, [a_navigate_step(str(uuid4()))])
    run_id = start(owner, workflow_id, variables={}).json()["run_id"]

    refused = run_output(stranger, run_id)
    assert refused.status_code == 404
    assert refused.json()["code"] == "run_not_found"


def test_any_member_of_the_run_organization_reads_output(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    extract_id = str(uuid4())
    workflow_id = published(
        owner,
        [a_scalar_extract(extract_id, "total")],
    )
    run_id = start(owner, workflow_id, variables={}).json()["run_id"]
    add_extract(run_id, extract_id, 0, "12.00")

    as_json = run_output(member, run_id)
    assert as_json.status_code == 200, as_json.text
    assert as_json.json() == {"total": "12.00"}
