"""The Worker credential path and takeover consent, at the HTTP seam."""

import logging
from uuid import UUID, uuid4

import pytest
from conftest import Account, join
from sqlalchemy import select
from step_by_step_api import clock
from step_by_step_api.accounts.models import User
from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.auth_states.store import store
from step_by_step_api.runs.models import Run, RunStatus, RunTrigger
from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope
from step_by_step_worker.store import PostgresRunStore
from test_auth_states import blob as auth_blob
from test_runs import detail, start
from test_secrets import bind, create
from test_workflow_versions import publish
from test_workflows import NewAccount, a_navigate_step, a_workflow, save_draft

pytestmark = pytest.mark.integration
DISPATCH_LIST = "runs:dispatch"
TOKEN = "test-internal-token"
SECRET_VALUE = "vault-zx9q2m-plaintext"
OVERRIDE_VALUE = "personal-zx9q2m-override"


@pytest.fixture(autouse=True)
def empty_dispatch_list() -> None:
    get_redis().delete(DISPATCH_LIST)


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", TOKEN)


def headers(token: str | None = TOKEN) -> dict[str, str]:
    if token is None:
        return {}
    return {"Authorization": f"Bearer {token}"}


def credentials(client, run_id: str, *, token: str | None = TOKEN):
    return client.get(f"/internal/runs/{run_id}/credentials", headers=headers(token))


def consents(client, run_id: str, *, token: str | None = TOKEN):
    return client.get(
        f"/internal/runs/{run_id}/auth-state-consents", headers=headers(token)
    )


def write_back(
    client,
    run_id: str,
    *,
    states: list[dict[str, object]] | None = None,
    new_candidates: list[str] | None = None,
    token: str | None = TOKEN,
):
    return client.post(
        f"/internal/runs/{run_id}/auth-states",
        json={"states": states or [], "new_candidates": new_candidates or []},
        headers=headers(token),
    )


def user_id(account: Account) -> UUID:
    with session_scope() as db:
        return db.execute(
            select(User.id).where(User.email == account.email)
        ).scalar_one()


def published_with_secret(account: Account, secret: dict[str, object]) -> str:
    workflow_id = a_workflow(account)
    bind(account, workflow_id, secret)
    saved = save_draft(
        account,
        workflow_id,
        steps=[a_navigate_step(str(uuid4()))],
        variables=[
            {
                "name": "password",
                "secret": True,
                "secretId": secret["id"],
                "secretName": secret["name"],
            }
        ],
    )
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201
    return workflow_id


def published_naming(account: Account, url: str) -> str:
    workflow_id = a_workflow(account)
    saved = save_draft(
        account,
        workflow_id,
        steps=[
            {
                "id": str(uuid4()),
                "type": "navigate",
                "label": "Go",
                "payload": {"url": url},
            }
        ],
    )
    assert saved.status_code == 200, saved.text
    assert publish(account, workflow_id).status_code == 201
    return workflow_id


def claim(run_id: str) -> None:
    work = PostgresRunStore().claim(
        UUID(run_id), "worker-1", "worker-1:5900", clock.now()
    )
    assert work is not None


def claimed_manual(account: Account, workflow_id: str) -> str:
    run_id = start(account, workflow_id, variables={}).json()["run_id"]
    claim(run_id)
    return run_id


def claimed_scheduled(account: Account, workflow_id: str) -> str:
    with session_scope() as db:
        run = Run(
            org_id=UUID(account.org_id),
            starter_user_id=None,
            workflow_id=UUID(workflow_id),
            version_number=1,
            trigger=RunTrigger.SCHEDULE,
            status=RunStatus.QUEUED,
            variables={},
        )
        db.add(run)
        db.commit()
        run_id = str(run.id)
    claim(run_id)
    return run_id


def cookie_by_domain(payload: dict[str, object]) -> dict[str, str]:
    states = payload["auth_states"]
    assert isinstance(states, list)
    return {
        str(state["domain"]): str(state["cookies"][0]["value"])
        for state in states
        if isinstance(state, dict)
    }


def sealed_layer(org_id: str, domain: str, owner: UUID | None) -> bytes:
    with session_scope() as db:
        query = select(AuthState).where(
            AuthState.org_id == UUID(org_id), AuthState.domain == domain
        )
        query = (
            query.where(AuthState.user_id.is_(None))
            if owner is None
            else query.where(AuthState.user_id == owner)
        )
        row = db.execute(query).scalar_one()
        return bytes(row.sealed_blob)


def test_internal_credential_routes_need_the_token_and_a_live_assigned_run(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_naming(account, "https://a.com")
    queued_id = start(account, workflow_id, variables={}).json()["run_id"]
    live_id = claimed_manual(account, workflow_id)
    failed_id = claimed_manual(account, workflow_id)
    with session_scope() as db:
        run = db.get(Run, UUID(failed_id))
        assert run is not None
        run.status = RunStatus.FAILED
        db.commit()

    for run_id in (queued_id, live_id, failed_id):
        assert credentials(account.client, run_id, token=None).status_code == 401
        assert consents(account.client, run_id, token=None).status_code == 401
        assert write_back(account.client, run_id, token=None).status_code == 401

    for run_id in (queued_id, failed_id):
        assert credentials(account.client, run_id).status_code == 409
        assert consents(account.client, run_id).status_code == 409
        assert write_back(account.client, run_id).status_code == 409

    assert credentials(account.client, live_id).status_code == 200
    assert consents(account.client, live_id).status_code == 200


def test_credentials_injects_the_resolved_union_not_the_version_urls(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    starter = join(owner, new_account())
    with session_scope() as db:
        org = UUID(owner.org_id)
        store(db, org, None, auth_blob("a.com", "org-a"))
        store(db, org, None, auth_blob("b.com", "org-b"))
        store(db, org, user_id(starter), auth_blob("a.com", "personal-a"))
        store(db, org, user_id(starter), auth_blob("c.com", "personal-c"))
        db.commit()
    workflow_id = published_naming(starter, "https://a.com/app")
    run_id = claimed_manual(starter, workflow_id)

    payload = credentials(starter.client, run_id)

    assert payload.status_code == 200, payload.text
    assert cookie_by_domain(payload.json()) == {
        "a.com": "personal-a",
        "b.com": "org-b",
        "c.com": "personal-c",
    }


def test_credentials_resolves_overrides_only_for_the_starter(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    starter = join(owner, new_account())
    other = join(owner, new_account())
    secret = create(owner, value=SECRET_VALUE).json()
    assert (
        starter.client.put(
            f"/api/secrets/{secret['id']}/override", json={"value": OVERRIDE_VALUE}
        ).status_code
        == 204
    )
    workflow_id = published_with_secret(owner, secret)

    starter_run = claimed_manual(starter, workflow_id)
    other_run = claimed_manual(other, workflow_id)
    scheduled_run = claimed_scheduled(owner, workflow_id)

    starter_payload = credentials(starter.client, starter_run)
    other_payload = credentials(other.client, other_run)
    scheduled_payload = credentials(owner.client, scheduled_run)

    assert starter_payload.status_code == 200, starter_payload.text
    assert starter_payload.json()["secrets"] == [
        {"variable_name": "password", "value": OVERRIDE_VALUE}
    ]
    assert other_payload.json()["secrets"] == [
        {"variable_name": "password", "value": SECRET_VALUE}
    ]
    assert scheduled_payload.json()["secrets"] == [
        {"variable_name": "password", "value": SECRET_VALUE}
    ]


def test_renaming_a_bound_secret_keeps_the_variable_name(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner, name="acme-portal-password", value=SECRET_VALUE).json()
    workflow_id = published_with_secret(owner, secret)
    assert (
        owner.client.patch(
            f"/api/secrets/{secret['id']}", json={"name": "portal-password"}
        ).status_code
        == 200
    )
    run_id = claimed_manual(owner, workflow_id)

    payload = credentials(owner.client, run_id)

    assert payload.status_code == 200, payload.text
    assert payload.json()["secrets"] == [
        {"variable_name": "password", "value": SECRET_VALUE}
    ]


def test_a_deleted_secret_is_missing_secret_on_credentials(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner, value=SECRET_VALUE).json()
    assert (
        owner.client.put(
            f"/api/secrets/{secret['id']}/override", json={"value": OVERRIDE_VALUE}
        ).status_code
        == 204
    )
    workflow_id = published_with_secret(owner, secret)
    run_id = start(owner, workflow_id, variables={}).json()["run_id"]
    assert owner.client.delete(f"/api/secrets/{secret['id']}").status_code == 204
    claim(run_id)

    refused = credentials(owner.client, run_id)

    assert refused.status_code == 409
    assert refused.json()["code"] == "missing_secret"
    assert refused.json()["variable_names"] == ["password"]


def test_starting_a_run_whose_secret_is_gone_creates_nothing(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner, value=SECRET_VALUE).json()
    workflow_id = published_with_secret(owner, secret)
    assert owner.client.delete(f"/api/secrets/{secret['id']}").status_code == 204
    before = owner.client.get("/api/runs", params={"workflow_id": workflow_id})

    refused = start(owner, workflow_id, variables={})
    after = owner.client.get("/api/runs", params={"workflow_id": workflow_id})

    assert refused.status_code == 409
    assert refused.json()["code"] == "missing_secret"
    assert refused.json()["variable_names"] == ["password"]
    assert after.json()["items"] == before.json()["items"]


def test_write_back_refreshes_the_resolved_layer_only(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    starter = join(owner, new_account())
    starter_id = user_id(starter)
    with session_scope() as db:
        org = UUID(owner.org_id)
        store(db, org, None, auth_blob("a.com", "org-a"))
        store(db, org, None, auth_blob("b.com", "org-b"))
        store(db, org, starter_id, auth_blob("a.com", "personal-a"))
        db.commit()
    org_a_before = sealed_layer(owner.org_id, "a.com", None)
    org_b_before = sealed_layer(owner.org_id, "b.com", None)
    personal_before = sealed_layer(owner.org_id, "a.com", starter_id)
    workflow_id = published_naming(starter, "https://a.com")
    member_run = claimed_manual(starter, workflow_id)
    scheduled_run = claimed_scheduled(owner, workflow_id)

    member = write_back(
        starter.client,
        member_run,
        states=[
            auth_blob("a.com", "personal-a-new").model_dump(mode="json", by_alias=True),
            auth_blob("b.com", "org-b-new").model_dump(mode="json", by_alias=True),
        ],
    )

    assert member.status_code == 204, member.text
    assert sealed_layer(owner.org_id, "a.com", None) == org_a_before
    assert sealed_layer(owner.org_id, "b.com", None) != org_b_before
    personal_after_member = sealed_layer(owner.org_id, "a.com", starter_id)
    assert personal_after_member != personal_before

    scheduled = write_back(
        owner.client,
        scheduled_run,
        states=[
            auth_blob("a.com", "schedule-a-new").model_dump(mode="json", by_alias=True)
        ],
    )

    assert scheduled.status_code == 204, scheduled.text
    assert sealed_layer(owner.org_id, "a.com", None) != org_a_before
    assert sealed_layer(owner.org_id, "a.com", starter_id) == personal_after_member


def test_write_back_without_a_record_or_consent_is_rejected(
    new_account: NewAccount,
) -> None:
    account = new_account()
    run_id = claimed_manual(account, published_naming(account, "https://a.com"))

    refused = write_back(
        account.client,
        run_id,
        states=[
            auth_blob("newsite.test", "fresh").model_dump(mode="json", by_alias=True)
        ],
    )

    assert refused.status_code == 400
    assert refused.json()["code"] == "unconsented_domain"
    assert refused.json()["domain"] == "newsite.test"
    assert account.client.get("/api/auth-states").json() == []


def test_consent_makes_a_new_domain_writable_at_the_chosen_scope(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    org_run = claimed_manual(owner, published_naming(owner, "https://a.com"))
    personal_run = claimed_manual(member, published_naming(member, "https://a.com"))

    assert (
        write_back(owner.client, org_run, new_candidates=["keep-org.test"]).status_code
        == 204
    )
    assert (
        write_back(
            member.client, personal_run, new_candidates=["keep-me.test"]
        ).status_code
        == 204
    )
    org_seen = consents(owner.client, org_run)
    personal_seen = consents(member.client, personal_run)
    org_detail = detail(owner, org_run).json()["auth_state_candidates"]
    personal_detail = detail(member, personal_run).json()["auth_state_candidates"]

    assert org_seen.json() == {"domains": []}
    assert personal_seen.json() == {"domains": []}
    assert org_detail == [{"domain": "keep-org.test", "consent": None}]
    assert personal_detail == [{"domain": "keep-me.test", "consent": None}]

    org_consent = owner.client.post(
        f"/api/runs/{org_run}/auth-state-consents",
        json={"domain": "keep-org.test", "scope": "organization"},
    )
    personal_consent = member.client.post(
        f"/api/runs/{personal_run}/auth-state-consents",
        json={"domain": "keep-me.test", "scope": "personal"},
    )

    assert org_consent.status_code == 204, org_consent.text
    assert personal_consent.status_code == 204, personal_consent.text
    assert consents(owner.client, org_run).json() == {"domains": ["keep-org.test"]}
    assert consents(member.client, personal_run).json() == {"domains": ["keep-me.test"]}
    assert detail(owner, org_run).json()["auth_state_candidates"] == [
        {"domain": "keep-org.test", "consent": {"scope": "organization"}}
    ]

    org_write = write_back(
        owner.client,
        org_run,
        states=[
            auth_blob("keep-org.test", "org-kept").model_dump(
                mode="json", by_alias=True
            )
        ],
    )
    personal_write = write_back(
        member.client,
        personal_run,
        states=[
            auth_blob("keep-me.test", "personal-kept").model_dump(
                mode="json", by_alias=True
            )
        ],
    )

    assert org_write.status_code == 204, org_write.text
    assert personal_write.status_code == 204, personal_write.text
    listed = member.client.get("/api/auth-states").json()
    by_domain = {row["domain"]: row["scope"] for row in listed}
    assert by_domain["keep-org.test"] == "organization"
    assert by_domain["keep-me.test"] == "personal"
    owner_listed = {
        row["domain"] for row in owner.client.get("/api/auth-states").json()
    }
    assert "keep-me.test" not in owner_listed


def test_consent_refuses_unknown_domains_and_personal_scope_without_a_starter(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = published_naming(account, "https://a.com")
    member_run = claimed_manual(account, workflow_id)
    scheduled_run = claimed_scheduled(account, workflow_id)
    assert (
        write_back(
            account.client, scheduled_run, new_candidates=["keep-org.test"]
        ).status_code
        == 204
    )

    missing = account.client.post(
        f"/api/runs/{member_run}/auth-state-consents",
        json={"domain": "keep-org.test", "scope": "organization"},
    )
    personal_on_schedule = account.client.post(
        f"/api/runs/{scheduled_run}/auth-state-consents",
        json={"domain": "keep-org.test", "scope": "personal"},
    )

    assert missing.status_code == 404
    assert missing.json()["code"] == "not_a_candidate"
    assert personal_on_schedule.status_code == 422
    assert personal_on_schedule.json()["code"] == "no_starter"


def test_a_failed_run_cannot_write_auth_state_back(
    new_account: NewAccount,
) -> None:
    account = new_account()
    with session_scope() as db:
        store(db, UUID(account.org_id), None, auth_blob("a.com", "org-a"))
        db.commit()
    before = sealed_layer(account.org_id, "a.com", None)
    run_id = claimed_manual(account, published_naming(account, "https://a.com"))
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = RunStatus.FAILED
        db.commit()

    refused = write_back(
        account.client,
        run_id,
        states=[auth_blob("a.com", "poison").model_dump(mode="json", by_alias=True)],
    )

    assert refused.status_code == 409
    assert sealed_layer(account.org_id, "a.com", None) == before


def test_credentials_plaintext_does_not_appear_in_logs(
    new_account: NewAccount,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = new_account()
    secret = create(owner, value=SECRET_VALUE).json()
    workflow_id = published_with_secret(owner, secret)
    with session_scope() as db:
        store(db, UUID(owner.org_id), None, auth_blob("a.com", "cookie-zx9q2m"))
        db.commit()
    run_id = claimed_manual(owner, workflow_id)

    with caplog.at_level(logging.DEBUG):
        payload = credentials(owner.client, run_id)

    assert payload.status_code == 200, payload.text
    assert SECRET_VALUE in str(payload.json()["secrets"])
    written = caplog.text + capsys.readouterr().out + capsys.readouterr().err
    assert SECRET_VALUE not in written
    assert "cookie-zx9q2m" not in written
