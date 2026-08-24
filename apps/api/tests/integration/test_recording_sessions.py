"""Recording sessions at their public seam: HTTP against the app and Postgres."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from conftest import Account

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


def a_workflow(account: Account) -> str:
    created = account.client.post("/api/workflows", json={"name": "Invoices"})
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def mint(
    account: Account,
    workflow_id: str,
    *,
    version: str | None = "0.1.0",
    body: dict[str, object] | None = None,
):
    headers = {"X-Extension-Version": version} if version is not None else {}
    return account.client.post(
        f"/api/workflows/{workflow_id}/recording-sessions",
        headers=headers,
        json=body or {},
    )


def test_mint_requires_a_supported_extension_version(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    declared = account.client.get("/api/extension/version").json()["minimum_supported"]

    missing = mint(account, workflow_id, version=None)
    old = mint(account, workflow_id, version="0.0.9")
    accepted = mint(account, workflow_id, version=declared)

    assert missing.status_code == 400, missing.text
    assert missing.json()["code"] == "extension_version_required"
    assert old.status_code == 409, old.text
    assert old.json()["code"] == "extension_update_required"
    assert "/extension" in old.json()["message"]
    assert accepted.status_code == 201, accepted.text
    assert set(accepted.json()) == {"session_id", "token"}


def a_navigate_step(label: str) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "type": "navigate",
        "label": label,
        "payload": {"url": f"https://example.test/{label}"},
    }


def token_headers(token: str) -> dict[str, str]:
    return {"Authorization": token}


def checkpoint(account: Account, session_id: str, token: str, seq: int, steps: list):
    return account.client.post(
        f"/api/recording-sessions/{session_id}/checkpoint",
        headers=token_headers(token),
        json={"seq": seq, "steps": steps},
    )


def finalize(account: Account, session_id: str, token: str, **body: object):
    return account.client.post(
        f"/api/recording-sessions/{session_id}/finalize",
        headers=token_headers(token),
        json=body,
    )


def test_checkpoints_keep_the_newest_full_buffer_and_finalize_replaces_the_draft(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    issued = mint(account, workflow_id).json()
    first = [a_navigate_step("one"), a_navigate_step("two")]
    stale_duplicate = [a_navigate_step("wrong")]
    complete = [*first, a_navigate_step("three"), a_navigate_step("four")]

    assert (
        checkpoint(account, issued["session_id"], issued["token"], 3, first).status_code
        == 204
    )
    assert (
        checkpoint(
            account, issued["session_id"], issued["token"], 3, stale_duplicate
        ).status_code
        == 204
    )
    assert (
        checkpoint(
            account, issued["session_id"], issued["token"], 4, complete
        ).status_code
        == 204
    )

    saved = finalize(account, issued["session_id"], issued["token"], variables=[])

    assert saved.status_code == 200, saved.text
    assert saved.json()["steps"] == complete
    assert (
        account.client.get(f"/api/workflows/{workflow_id}/draft").json() == saved.json()
    )


def test_an_expired_token_can_be_reminted_without_losing_the_checkpoint(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    now = datetime(2026, 8, 24, tzinfo=UTC)
    monkeypatch.setattr("step_by_step_api.clock.now", lambda: now)
    issued = mint(account, workflow_id).json()
    steps = [a_navigate_step("one"), a_navigate_step("two")]
    assert (
        checkpoint(account, issued["session_id"], issued["token"], 1, steps).status_code
        == 204
    )

    now += timedelta(hours=1, seconds=1)
    expired = checkpoint(account, issued["session_id"], issued["token"], 2, steps)
    renewed = mint(
        account,
        workflow_id,
        body={"session_id": issued["session_id"]},
    )

    assert expired.status_code == 401
    assert renewed.status_code == 201, renewed.text
    assert renewed.json()["session_id"] == issued["session_id"]
    saved = finalize(
        account,
        issued["session_id"],
        renewed.json()["token"],
        variables=[],
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["steps"] == steps


def test_finalize_refuses_an_unresolved_needs_secret_marker(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    issued = mint(account, workflow_id).json()
    step = {
        "id": str(uuid4()),
        "type": "type",
        "label": "Type password",
        "needsSecret": True,
        "payload": {
            "target": {"candidates": [{"kind": "label", "value": "Password"}]},
            "value": "",
        },
    }

    refused = finalize(
        account,
        issued["session_id"],
        issued["token"],
        steps=[step],
        variables=[],
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "needs_secret"
    assert (
        account.client.get(f"/api/workflows/{workflow_id}/draft").json()["steps"] == []
    )


def test_a_repick_finalize_changes_only_the_scoped_steps_candidates(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    target_id = str(uuid4())
    other_id = str(uuid4())
    old_candidates = [{"kind": "css", "value": "#save"}]
    target = {
        "id": target_id,
        "type": "click",
        "label": "Save",
        "payload": {"target": {"candidates": old_candidates}},
    }
    other = {
        "id": other_id,
        "type": "click",
        "label": "Cancel",
        "payload": {"target": {"candidates": [{"kind": "text", "value": "Cancel"}]}},
    }
    saved = account.client.put(
        f"/api/workflows/{workflow_id}/draft",
        json={"steps": [target, other], "variables": []},
    )
    assert saved.status_code == 200, saved.text
    before = saved.json()
    issued = mint(
        account,
        workflow_id,
        body={"mode": "repick", "step_id": target_id},
    ).json()
    fresh = [
        {"kind": "testid", "value": "save"},
        {"kind": "role", "value": "button[name='Save']"},
    ]

    patched = finalize(
        account,
        issued["session_id"],
        issued["token"],
        candidates=fresh,
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["steps"][0]["id"] == target_id
    assert patched.json()["steps"][0]["payload"]["target"]["candidates"] == fresh
    assert patched.json()["steps"][1] == before["steps"][1]
    before["steps"][0]["payload"]["target"]["candidates"] = fresh
    assert patched.json() == before


def test_a_token_opens_only_the_session_it_was_minted_for(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    other = new_account()
    owner_session = mint(owner, a_workflow(owner)).json()
    other_session = mint(other, a_workflow(other)).json()

    refused = checkpoint(
        other,
        other_session["session_id"],
        owner_session["token"],
        1,
        [a_navigate_step("stolen")],
    )

    assert refused.status_code == 401, refused.text
    assert refused.json()["code"] == "invalid_recording_token"
