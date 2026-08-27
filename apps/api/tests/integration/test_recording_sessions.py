"""Recording sessions at their public seam: HTTP against the app and Postgres."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from conftest import Account
from sqlalchemy import select
from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.auth_states.store import open_blob
from step_by_step_api.workflows.models import Workflow
from step_by_step_core.db import session_scope

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


def create_recording_secret(
    account: Account, session_id: str, token: str, name: str, value: str
):
    return account.client.post(
        f"/api/recording-sessions/{session_id}/secrets",
        headers=token_headers(token),
        json={"name": name, "value": value},
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


def test_recording_creates_and_binds_an_organization_secret_without_storing_its_value(
    new_account: NewAccount,
) -> None:
    account = new_account()
    other = new_account()
    workflow_id = a_workflow(account)
    issued = mint(account, workflow_id).json()
    other_issued = mint(other, a_workflow(other)).json()
    literal = "one-request-only"
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
    assert (
        checkpoint(
            account, issued["session_id"], issued["token"], 1, [step]
        ).status_code
        == 204
    )

    created = create_recording_secret(
        account, issued["session_id"], issued["token"], "Portal password", literal
    )

    assert created.status_code == 201, created.text
    identity = created.json()
    assert identity["name"] == "Portal password"
    listed = account.client.get("/api/secrets")
    assert listed.status_code == 200, listed.text
    assert [(row["id"], row["name"]) for row in listed.json()] == [
        (identity["id"], "Portal password")
    ]
    assert other.client.get("/api/secrets").json() == []
    revealed = account.client.post(f"/api/secrets/{identity['id']}/reveal")
    assert revealed.json() == {"value": literal}

    duplicate = create_recording_secret(
        account, issued["session_id"], issued["token"], "Portal password", "different"
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "name_taken"
    foreign = create_recording_secret(
        account,
        issued["session_id"],
        other_issued["token"],
        "Foreign",
        "not-stored",
    )
    assert foreign.status_code == 401

    ordinary_step = dict(step)
    ordinary_step.pop("needsSecret")
    ordinary_step["payload"] = {
        **step["payload"],
        "value": "{{password}}",
    }
    variable = {
        "name": "password",
        "secret": True,
        "secretId": identity["id"],
        "secretName": identity["name"],
    }
    saved = finalize(
        account,
        issued["session_id"],
        issued["token"],
        steps=[ordinary_step],
        variables=[variable],
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["variables"] == [variable]
    assert literal not in saved.text
    assert literal not in str(
        account.client.get(f"/api/workflows/{workflow_id}/draft").json()
    )

    finalized = create_recording_secret(
        account, issued["session_id"], issued["token"], "Too late", "not-stored"
    )
    assert finalized.status_code == 409
    assert finalized.json()["code"] == "recording_session_finalized"


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


def auth_blob(domain: str, value: str) -> dict[str, object]:
    return {
        "domain": domain,
        "cookies": [
            {
                "name": "session",
                "value": value,
                "domain": f".{domain}",
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
                "partitionKey": {"topLevelSite": f"https://{domain}"},
            }
        ],
        "origins": [
            {
                "origin": f"https://app.{domain}",
                "local_storage": [{"name": "local", "value": value}],
            }
        ],
        "session_storage": [
            {
                "origin": f"https://app.{domain}",
                "items": [{"name": "session", "value": value}],
            }
        ],
    }


def test_capture_options_and_upload_use_the_recording_member_and_organization(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    first = mint(account, workflow_id).json()

    options = account.client.post(
        f"/api/recording-sessions/{first['session_id']}/auth-state-options",
        headers=token_headers(first["token"]),
        json={
            "hosts": ["www.example.co.uk", "app.example.co.uk", "accounts.google.com"]
        },
    )
    assert options.status_code == 200, options.text
    assert options.json() == [
        {
            "domain": "example.co.uk",
            "organization_saved_at": None,
            "personal_saved_at": None,
        },
        {
            "domain": "google.com",
            "organization_saved_at": None,
            "personal_saved_at": None,
        },
    ]

    captured = account.client.post(
        f"/api/recording-sessions/{first['session_id']}/auth-states",
        headers=token_headers(first["token"]),
        json={
            "captures": [
                {**auth_blob("example.co.uk", "org-one"), "scope": "organization"},
                {**auth_blob("example.co.uk", "mine-example"), "scope": "personal"},
                {**auth_blob("google.com", "mine-one"), "scope": "personal"},
            ]
        },
    )
    assert captured.status_code == 204, captured.text
    existing = account.client.post(
        f"/api/recording-sessions/{first['session_id']}/auth-state-options",
        headers=token_headers(first["token"]),
        json={"hosts": ["app.example.co.uk"]},
    ).json()[0]
    assert existing["organization_saved_at"] is not None
    assert existing["personal_saved_at"] is not None

    with session_scope() as db:
        workflow = db.get_one(Workflow, UUID(workflow_id))
        rows = list(
            db.execute(
                select(AuthState)
                .where(AuthState.org_id == workflow.org_id)
                .order_by(AuthState.domain)
            ).scalars()
        )
        rows.sort(key=lambda row: (row.domain, row.user_id is not None))
        assert [(row.domain, row.user_id is None) for row in rows] == [
            ("example.co.uk", True),
            ("example.co.uk", False),
            ("google.com", False),
        ]
        org_blob = open_blob(rows[0])
        assert org_blob.cookies[0].http_only is True
        assert org_blob.cookies[0].partition_key == {
            "topLevelSite": "https://example.co.uk"
        }
        assert org_blob.origins[0].local_storage[0].value == "org-one"
        assert org_blob.session_storage[0].items[0].value == "org-one"
        org_id = rows[0].id
        untouched_ids = {rows[1].id, rows[2].id}
        org_created_at = rows[0].created_at
        org_scope = workflow.org_id

    second = mint(account, workflow_id).json()
    replaced = account.client.post(
        f"/api/recording-sessions/{second['session_id']}/auth-states",
        headers=token_headers(second["token"]),
        json={
            "captures": [
                {**auth_blob("example.co.uk", "org-two"), "scope": "organization"}
            ]
        },
    )
    assert replaced.status_code == 204, replaced.text
    with session_scope() as db:
        rows = (
            db.execute(select(AuthState).where(AuthState.org_id == org_scope))
            .scalars()
            .all()
        )
        by_id = {row.id: row for row in rows}
        assert set(by_id) == {org_id, *untouched_ids}
        assert by_id[org_id].created_at == org_created_at
        assert open_blob(by_id[org_id]).cookies[0].value == "org-two"
        assert {
            open_blob(by_id[row_id]).cookies[0].value for row_id in untouched_ids
        } == {"mine-example", "mine-one"}

    finalized = finalize(
        account, second["session_id"], second["token"], steps=[], variables=[]
    )
    assert finalized.status_code == 200, finalized.text
    refused = account.client.post(
        f"/api/recording-sessions/{second['session_id']}/auth-states",
        headers=token_headers(second["token"]),
        json={
            "captures": [
                {**auth_blob("example.co.uk", "too-late"), "scope": "organization"}
            ]
        },
    )
    assert refused.status_code == 409
    foreign = account.client.post(
        f"/api/recording-sessions/{first['session_id']}/auth-states",
        headers=token_headers(second["token"]),
        json={
            "captures": [
                {**auth_blob("example.co.uk", "foreign"), "scope": "organization"}
            ]
        },
    )
    assert foreign.status_code == 401


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
