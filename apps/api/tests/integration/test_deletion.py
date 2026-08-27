"""Leaving, at its seam: HTTP against the app, with a real Postgres.

External behaviour only — an Organization ends, an account ends, and what a
test reads afterwards is what a client can ask for. Two tests do look in a
table, and both assert what a table must *not* hold: an absence is the one
claim no HTTP answer can carry, and "nothing references the person who left"
is the whole point of this slice.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from conftest import Account, code_sent_to, join
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from step_by_step_api import clock
from step_by_step_api.auth_states.store import store as store_auth_state
from step_by_step_api.loop import tick
from step_by_step_api.main import app
from step_by_step_api.runs.models import RunStatus
from step_by_step_core.db import session_scope
from step_by_step_worker.store import PostgresRunStore
from test_auth_states import blob as auth_blob
from test_batches import create_batch
from test_run_artifacts import object_missing, seed_artifact, set_status
from test_run_credentials import credentials, published_with_secret
from test_runs import detail, published_workflow, start
from test_schedules import create_schedule, runs_of
from test_secrets import create

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


@pytest.fixture
def owned_keys() -> Iterator[list[str]]:
    """Garage keys this test owns, removed if the behavior under test leaves them."""
    from step_by_step_core.objects import artifact_bucket, object_store

    keys: list[str] = []
    yield keys
    for key in keys:
        object_store().delete_object(Bucket=artifact_bucket(), Key=key)


def end_organization(actor: Account, confirmation: str) -> Response:
    """Delete the Organization the actor acts in, typing its name to mean it.

    `request` rather than `delete`, because httpx's shorthand for this method
    carries no body — and the confirmation is the body.
    """
    return actor.client.request(
        "DELETE",
        f"/api/orgs/{actor.org_id}",
        json={"name_confirmation": confirmation},
    )


def end_account(actor: Account, confirmation: str) -> Response:
    """Delete the actor's own account, typing its address to mean it."""
    return actor.client.request(
        "DELETE", "/api/account", json={"email_confirmation": confirmation}
    )


def orgs_of(account: Account) -> dict[str, str]:
    """Every Organization this account acts in, with the role it has there."""
    me = account.client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return {org["id"]: org["role"] for org in me.json()["orgs"]}


def org_name_of(account: Account) -> str:
    """What the Organization is called — the name its owner has to type."""
    me = account.client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return next(org["name"] for org in me.json()["orgs"] if org["id"] == account.org_id)


def refusal_of(answer: Response) -> str:
    """The machine-readable code a client acts on, and never the prose."""
    return str(answer.json()["code"])


def test_a_mistyped_name_ends_nothing(
    new_account: NewAccount, owned_keys: list[str]
) -> None:
    owner = new_account()
    run_id = start(owner, published_workflow(owner), variables={}).json()["run_id"]
    artifact = seed_artifact(UUID(run_id), owned_keys)

    refused = end_organization(owner, org_name_of(owner)[:-1])

    assert refused.status_code == 400, refused.text
    assert refusal_of(refused) == "confirmation_mismatch"
    assert owner.org_id in orgs_of(owner)
    assert not object_missing(artifact.object_key)


def test_only_the_owner_may_end_an_organization(new_account: NewAccount) -> None:
    owner = new_account()
    name = org_name_of(owner)
    admin = join(owner, new_account(), role="admin")
    member = join(owner, new_account())

    for actor in (admin, member):
        refused = end_organization(actor, name)

        assert refused.status_code == 403, refused.text
        assert refusal_of(refused) == "not_the_owner"
    assert owner.org_id in orgs_of(owner)


def test_ending_an_organization_takes_its_memberships_and_invitations(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    name = org_name_of(owner)
    newcomer = new_account()
    own_org = newcomer.org_id
    member = join(owner, newcomer)
    invitee = new_account()
    offered = owner.client.post(
        f"/api/orgs/{owner.org_id}/invitations",
        json={"email": invitee.email, "role": "member"},
    )
    assert offered.status_code == 201, offered.text

    ended = end_organization(owner, name)

    assert ended.status_code == 204, ended.text
    assert orgs_of(owner) == {}
    # The member kept their account, their session, and the Organization that
    # is theirs — what ended is the team, and only for as far as it reached.
    assert orgs_of(member) == {own_org: "owner"}
    assert member.client.get(f"/api/orgs/{owner.org_id}/members").status_code == 403
    standing = invitee.client.get("/api/auth/me")
    assert standing.status_code == 200, standing.text
    assert standing.json()["invitations"] == []
    taken = invitee.client.post(f"/api/invitations/{offered.json()['id']}/accept")
    assert taken.status_code == 404, taken.text


def references_to(table: str, gone: str) -> dict[str, int]:
    """Every row, in any table, that still points at an id that is gone.

    Read out of Postgres's own catalogue rather than out of a list of tables
    kept here, because the claim this slice makes is about the convention and
    not about today's six tables: whatever joins the cascade later is asked
    about by the same test, and a table wired up without `ON DELETE CASCADE`
    fails it the day it lands.
    """
    with session_scope() as db:
        pointing = db.execute(
            text(
                "SELECT (SELECT relname FROM pg_class WHERE oid = con.conrelid),"
                "       (SELECT attname FROM pg_attribute"
                "          WHERE attrelid = con.conrelid AND attnum = con.conkey[1])"
                "  FROM pg_constraint con"
                " WHERE con.contype = 'f' AND con.confrelid = to_regclass(:target)"
            ),
            {"target": table},
        ).all()
        assert pointing, f"nothing references {table}; the query is wrong"
        left = {
            f"{referencing}.{column}": db.execute(
                text(f"SELECT count(*) FROM {referencing} WHERE {column} = :gone"),
                {"gone": gone},
            ).scalar_one()
            for referencing, column in pointing
        }
    return {where: count for where, count in left.items() if count}


def test_ending_an_organization_cancels_runs_then_purges_rows_and_objects(
    new_account: NewAccount, owned_keys: list[str]
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    offered = owner.client.post(
        f"/api/orgs/{owner.org_id}/invitations",
        json={"email": new_account().email, "role": "member"},
    )
    assert offered.status_code == 201, offered.text
    workflow_id = published_workflow(owner)
    secret = create(owner, value="shared").json()
    assert (
        member.client.put(
            f"/api/secrets/{secret['id']}/override", json={"value": "personal"}
        ).status_code
        == 204
    )
    with session_scope() as db:
        store_auth_state(
            db, UUID(owner.org_id), None, auth_blob("shared.test", "organization")
        )
        store_auth_state(
            db,
            UUID(owner.org_id),
            UUID(user_id_of(member)),
            auth_blob("personal.test", "member"),
        )
        db.commit()
    schedule = create_schedule(
        owner,
        workflow_id,
        cron="0 9 * * *",
        timezone="UTC",
        enabled=False,
    )
    assert schedule.status_code == 201, schedule.text
    batch = create_batch(owner, workflow_id, name="Purge me", rows=[{"variables": {}}])
    assert batch.status_code == 201, batch.text
    queued_id = start(owner, workflow_id, variables={}).json()["run_id"]
    running_id = start(owner, workflow_id, variables={}).json()["run_id"]
    set_status(running_id, RunStatus.RUNNING)
    queued_artifact = seed_artifact(UUID(queued_id), owned_keys)
    running_artifact = seed_artifact(UUID(running_id), owned_keys)

    ended = end_organization(owner, org_name_of(owner))

    assert ended.status_code == 204, ended.text
    assert references_to("organizations", owner.org_id) == {}
    assert object_missing(queued_artifact.object_key)
    assert object_missing(running_artifact.object_key)


def owning_nothing(host: Account, new_account: NewAccount) -> Account:
    """An account in somebody else's team, and the owner of no Organization.

    The state every account has to reach before it can be ended: it joined a
    team, and it ended the Organization its own signup made.
    """
    guest = new_account()
    own_org = guest.org_id
    join(host, guest)
    guest.client.headers["X-Organization"] = own_org
    ended = end_organization(guest, org_name_of(guest))
    assert ended.status_code == 204, ended.text
    return guest


def test_a_sole_owner_may_not_end_their_account(new_account: NewAccount) -> None:
    owner = new_account()

    refused = end_account(owner, owner.email)

    assert refused.status_code == 403, refused.text
    assert refusal_of(refused) == "sole_owner"
    assert orgs_of(owner) == {owner.org_id: "owner"}


def test_a_mistyped_address_ends_nothing(new_account: NewAccount) -> None:
    guest = owning_nothing(new_account(), new_account)

    refused = end_account(guest, f"not-{guest.email}")

    assert refused.status_code == 400, refused.text
    assert refusal_of(refused) == "confirmation_mismatch"
    assert guest.client.get("/api/auth/me").status_code == 200


def user_id_of(account: Account) -> str:
    """The account's own id, which is what a Membership is named by."""
    me = account.client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return str(me.json()["id"])


def member_ids_of(account: Account, org_id: str) -> set[str]:
    """Who the members screen of that Organization lists."""
    listed = account.client.get(f"/api/orgs/{org_id}/members")
    assert listed.status_code == 200, listed.text
    return {row["user_id"] for row in listed.json()}


def test_handing_the_organization_on_frees_the_account(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    heir = join(owner, new_account())
    handed = owner.client.post(
        f"/api/orgs/{owner.org_id}/transfer-ownership",
        json={"user_id": user_id_of(heir)},
    )
    assert handed.status_code == 204, handed.text

    ended = end_account(owner, owner.email)

    assert ended.status_code == 204, ended.text
    assert member_ids_of(heir, heir.org_id) == {user_id_of(heir)}


def test_removing_a_member_discards_their_personal_secret_override(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    secret = create(owner, value="shared-after-removal").json()
    set_override = member.client.put(
        f"/api/secrets/{secret['id']}/override", json={"value": "member-only"}
    )
    assert set_override.status_code == 204, set_override.text

    removed = owner.client.delete(
        f"/api/orgs/{owner.org_id}/members/{user_id_of(member)}"
    )

    assert removed.status_code == 204, removed.text
    assert owner.client.post(f"/api/secrets/{secret['id']}/reveal").json() == {
        "value": "shared-after-removal"
    }
    rejoined = join(owner, member)
    assert rejoined.client.get("/api/secrets").json()[0]["my_override"] is None
    missing = rejoined.client.post(f"/api/secrets/{secret['id']}/override/reveal")
    assert missing.status_code == 404
    assert missing.json()["code"] == "no_override"


def test_member_removal_leaves_running_and_scheduled_work_alone(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", "test-internal-token")
    owner = new_account()
    member = join(owner, new_account())
    secret = create(owner, value="shared").json()
    assert (
        member.client.put(
            f"/api/secrets/{secret['id']}/override", json={"value": "resolved-once"}
        ).status_code
        == 204
    )
    running_workflow = published_with_secret(owner, secret)
    run_id = start(member, running_workflow, variables={}).json()["run_id"]
    worker = PostgresRunStore()
    claimed = worker.claim(UUID(run_id), "worker-1", "worker-1:5900", clock.now())
    assert claimed is not None
    held = credentials(owner.client, run_id)
    assert held.json()["secrets"] == [
        {"variable_name": "password", "value": "resolved-once"}
    ]
    scheduled_workflow = published_workflow(owner)
    before_due = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "now", lambda: before_due)
    schedule = create_schedule(
        owner,
        scheduled_workflow,
        cron="* * * * *",
        timezone="UTC",
        enabled=True,
    )
    assert schedule.status_code == 201, schedule.text

    removed = owner.client.delete(
        f"/api/orgs/{owner.org_id}/members/{user_id_of(member)}"
    )
    worker.finish_run(UUID(run_id), "succeeded", None, None, 25, clock.now())
    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 8, 27, 12, 1, tzinfo=UTC))
    tick()

    assert removed.status_code == 204, removed.text
    finished = detail(owner, run_id)
    assert finished.status_code == 200, finished.text
    assert finished.json()["run"]["status"] == "succeeded"
    fired = runs_of(owner, scheduled_workflow)
    assert len(fired) == 1
    assert fired[0]["trigger"] == "schedule"


def test_ending_an_account_ends_its_sessions_and_its_memberships(
    new_account: NewAccount,
) -> None:
    host = new_account()
    guest = owning_nothing(host, new_account)
    guest_id = user_id_of(guest)

    ended = end_account(guest, guest.email)

    assert ended.status_code == 204, ended.text
    assert guest.client.get("/api/auth/me").status_code == 401
    assert guest_id not in member_ids_of(host, host.org_id)
    assert references_to("users", guest_id) == {}


def test_account_deletion_removes_overrides_from_every_membership_not_org_work(
    new_account: NewAccount,
) -> None:
    first = new_account()
    second = new_account()
    guest = owning_nothing(first, new_account)
    guest = join(second, guest)
    first_secret = create(first, name="first", value="first-shared").json()
    second_secret = create(second, name="second", value="second-shared").json()
    for host, secret in ((first, first_secret), (second, second_secret)):
        guest.client.headers["X-Organization"] = host.org_id
        assert (
            guest.client.put(
                f"/api/secrets/{secret['id']}/override", json={"value": "personal"}
            ).status_code
            == 204
        )
    first_workflow = published_workflow(first)
    second_workflow = published_workflow(second)

    ended = end_account(guest, guest.email)

    assert ended.status_code == 204, ended.text
    assert first.client.get(f"/api/workflows/{first_workflow}").status_code == 200
    assert second.client.get(f"/api/workflows/{second_workflow}").status_code == 200

    browser = TestClient(app)
    assert (
        browser.post("/api/auth/request-code", json={"email": guest.email}).status_code
        == 202
    )
    assert (
        browser.post(
            "/api/auth/verify-code",
            json={"email": guest.email, "code": code_sent_to(guest.email)},
        ).status_code
        == 200
    )
    fresh_org = browser.get("/api/auth/me").json()["orgs"][0]["id"]
    fresh = Account(client=browser, email=guest.email, org_id=fresh_org)
    for host in (first, second):
        rejoined = join(host, fresh)
        assert all(
            row["my_override"] is None
            for row in rejoined.client.get("/api/secrets").json()
        )


def test_the_address_can_sign_up_again_as_a_fresh_account(
    new_account: NewAccount,
) -> None:
    """Hard means hard: what comes back is a stranger with the same address."""
    host = new_account()
    guest = owning_nothing(host, new_account)
    address = guest.email
    assert end_account(guest, address).status_code == 204

    browser = TestClient(app)
    assert (
        browser.post("/api/auth/request-code", json={"email": address}).status_code
        == 202
    )
    signed_in = browser.post(
        "/api/auth/verify-code",
        json={"email": address, "code": code_sent_to(address)},
    )

    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json() == {"created": True}
    again = browser.get("/api/auth/me")
    assert again.status_code == 200, again.text
    assert [org["role"] for org in again.json()["orgs"]] == ["owner"]
    assert again.json()["id"] != user_id_of(host)
