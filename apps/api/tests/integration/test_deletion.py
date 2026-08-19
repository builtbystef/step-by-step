"""Leaving, at its seam: HTTP against the app, with a real Postgres.

External behaviour only — an Organization ends, an account ends, and what a
test reads afterwards is what a client can ask for. Two tests do look in a
table, and both assert what a table must *not* hold: an absence is the one
claim no HTTP answer can carry, and "nothing references the person who left"
is the whole point of this slice.
"""

from collections.abc import Callable

import pytest
from conftest import Account, code_sent_to, join
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from step_by_step_api.main import app
from step_by_step_core.db import session_scope

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


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


def test_a_mistyped_name_ends_nothing(new_account: NewAccount) -> None:
    owner = new_account()

    refused = end_organization(owner, org_name_of(owner)[:-1])

    assert refused.status_code == 400, refused.text
    assert refusal_of(refused) == "confirmation_mismatch"
    assert owner.org_id in orgs_of(owner)


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


def test_no_row_is_left_pointing_at_an_ended_organization(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    join(owner, new_account())
    offered = owner.client.post(
        f"/api/orgs/{owner.org_id}/invitations",
        json={"email": new_account().email, "role": "member"},
    )
    assert offered.status_code == 201, offered.text

    ended = end_organization(owner, org_name_of(owner))

    assert ended.status_code == 204, ended.text
    assert references_to("organizations", owner.org_id) == {}


def owning_nothing(host: Account, new_account: NewAccount) -> Account:
    """An account in somebody else's team, and the owner of no Organization.

    The state every account has to reach before it can be ended: it joined a
    team, and it ended the Organization its own signup made.
    """
    guest = new_account()
    join(host, guest)
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
