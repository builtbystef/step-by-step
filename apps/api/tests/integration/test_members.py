"""Membership management at its seam: HTTP against the app, with a real Postgres.

External behaviour only. Who is in an Organization, what each of them may do,
and what stops the moment a Membership ends — every one of them asked the way
the members screen asks it, and read by the machine-readable `code` a client
acts on.
"""

from collections.abc import Callable
from uuid import uuid4

import pytest
from conftest import Account, join
from httpx import Response

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


def members_of(account: Account, org_id: str | None = None) -> Response:
    """The Organization's people, as the members screen lists them."""
    return account.client.get(f"/api/orgs/{org_id or account.org_id}/members")


def roles_in(account: Account, org_id: str | None = None) -> dict[str, str]:
    """Who is in the Organization, by account id, and as what."""
    listed = members_of(account, org_id)
    assert listed.status_code == 200, listed.text
    return {row["user_id"]: row["role"] for row in listed.json()}


def user_id_of(account: Account) -> str:
    """The account's own id, which is what a Membership is named by."""
    me = account.client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return str(me.json()["id"])


def orgs_of(account: Account) -> dict[str, str]:
    """Every Organization this account acts in, with the role it has there."""
    me = account.client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return {org["id"]: org["role"] for org in me.json()["orgs"]}


def set_role(actor: Account, target: Account, role: str) -> Response:
    """Change what somebody may do in the Organization the actor names."""
    return actor.client.patch(
        f"/api/orgs/{actor.org_id}/members/{user_id_of(target)}", json={"role": role}
    )


def remove(actor: Account, target: Account) -> Response:
    """End a Membership — somebody else's, or the actor's own, which is leaving."""
    return actor.client.delete(f"/api/orgs/{actor.org_id}/members/{user_id_of(target)}")


def transfer(actor: Account, target_id: str) -> Response:
    """Hand the Organization to somebody else in it."""
    return actor.client.post(
        f"/api/orgs/{actor.org_id}/transfer-ownership", json={"user_id": target_id}
    )


def rename(actor: Account, name: str) -> Response:
    """Rename the Organization the actor names in the path."""
    return actor.client.patch(f"/api/orgs/{actor.org_id}", json={"name": name})


def domain_work_in(account: Account, org_id: str) -> Response:
    """A domain route, asked in the named Organization — the shared gate's ground.

    The Workflow it names is nobody's, so a caller the gate lets through meets
    404 `workflow_not_found` and one it refuses never reaches the route at all:
    the answer says which of the two happened without any Workflow existing.
    """
    return account.client.get(
        f"/api/workflows/{uuid4()}/draft", headers={"X-Organization": org_id}
    )


def test_any_member_lists_the_people_in_the_organization(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    assert (
        member.client.patch("/api/account", json={"display_name": "Grace"}).status_code
        == 200
    )

    listed = members_of(member)

    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert [row["email"] for row in rows] == [owner.email, member.email]
    assert [row["role"] for row in rows] == ["owner", "member"]
    assert [row["display_name"] for row in rows] == [None, "Grace"]
    assert rows[0]["user_id"] == user_id_of(owner)
    assert rows[0]["joined_at"] <= rows[1]["joined_at"]


def test_someone_outside_the_organization_sees_no_member_list(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()

    refused = members_of(stranger, owner.org_id)

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_a_member"


def test_an_owner_promotes_a_member_and_an_admin_demotes_one(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")
    member = join(owner, new_account())

    promoted = set_role(owner, member, "admin")
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "admin"
    assert roles_in(owner)[user_id_of(member)] == "admin"

    demoted = set_role(admin, member, "member")
    assert demoted.status_code == 200, demoted.text
    assert roles_in(owner)[user_id_of(member)] == "member"


def test_the_owners_role_is_not_an_admins_to_change(new_account: NewAccount) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")

    refused = set_role(admin, owner, "member")

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "is_owner"
    assert roles_in(owner)[user_id_of(owner)] == "owner"


def test_a_member_changes_nobodys_role(new_account: NewAccount) -> None:
    owner = new_account()
    member = join(owner, new_account())
    other = join(owner, new_account())

    refused = set_role(member, other, "admin")

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_an_admin"
    assert roles_in(owner)[user_id_of(other)] == "member"


def test_owner_is_not_a_role_anybody_may_hand_out(new_account: NewAccount) -> None:
    """Ownership transfers, and there is exactly one of it — so the role change
    route cannot express it at all."""
    owner = new_account()
    member = join(owner, new_account())

    refused = set_role(owner, member, "owner")

    assert refused.status_code == 422, refused.text
    assert roles_in(owner)[user_id_of(member)] == "member"


def test_a_removed_member_loses_the_organization_at_once(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    own_org = next(iter(set(orgs_of(member)) - {owner.org_id}))

    removed = remove(owner, member)

    assert removed.status_code == 204, removed.text
    assert removed.content == b""
    refused = domain_work_in(member, owner.org_id)
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_a_member"
    assert user_id_of(member) not in roles_in(owner)
    assert owner.org_id not in orgs_of(member)
    passed = domain_work_in(member, own_org)
    assert passed.status_code == 404, passed.text
    assert passed.json()["code"] == "workflow_not_found"


def test_an_admin_removes_a_member_and_a_member_removes_nobody(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")
    member = join(owner, new_account())
    other = join(owner, new_account())

    refused = remove(member, other)
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_an_admin"

    removed = remove(admin, other)
    assert removed.status_code == 204, removed.text
    assert user_id_of(other) not in roles_in(owner)


def test_the_owner_cannot_be_removed(new_account: NewAccount) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")

    refused = remove(admin, owner)

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "is_owner"
    assert roles_in(owner)[user_id_of(owner)] == "owner"


def test_a_member_and_an_admin_both_leave_on_their_own(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")
    member = join(owner, new_account())

    assert remove(admin, admin).status_code == 204
    left = remove(member, member)

    assert left.status_code == 204, left.text
    assert set(roles_in(owner)) == {user_id_of(owner)}
    gone = domain_work_in(member, owner.org_id)
    assert gone.status_code == 403, gone.text
    assert gone.json()["code"] == "not_a_member"


def test_the_owner_cannot_leave_the_organization(new_account: NewAccount) -> None:
    owner = new_account()
    join(owner, new_account(), role="admin")

    refused = remove(owner, owner)

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "is_owner"
    assert roles_in(owner)[user_id_of(owner)] == "owner"


def test_ownership_transfers_and_the_old_owner_becomes_an_admin(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())

    handed = transfer(owner, user_id_of(member))

    assert handed.status_code == 204, handed.text
    assert handed.content == b""
    roles = roles_in(owner)
    assert roles[user_id_of(member)] == "owner"
    assert roles[user_id_of(owner)] == "admin"
    assert list(roles.values()).count("owner") == 1
    assert orgs_of(member)[owner.org_id] == "owner"


def test_the_old_owner_may_leave_once_they_have_transferred(
    new_account: NewAccount,
) -> None:
    """The refusals follow the role, not the person: what stopped the owner
    stops whoever holds it now."""
    owner = new_account()
    member = join(owner, new_account())
    assert transfer(owner, user_id_of(member)).status_code == 204

    left = remove(owner, owner)

    assert left.status_code == 204, left.text
    assert set(roles_in(member)) == {user_id_of(member)}


def test_only_the_owner_hands_the_organization_on(new_account: NewAccount) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")
    member = join(owner, new_account())

    refused = transfer(admin, user_id_of(member))

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_the_owner"
    assert roles_in(owner)[user_id_of(owner)] == "owner"


def test_the_organization_is_handed_only_to_somebody_in_it(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = new_account()

    refused = transfer(owner, user_id_of(stranger))
    nobody = transfer(owner, str(uuid4()))

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "member_not_found"
    assert nobody.status_code == 404, nobody.text
    assert roles_in(owner)[user_id_of(owner)] == "owner"


def test_an_owner_and_an_admin_rename_the_organization(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")

    renamed = rename(owner, "Accounts payable")
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Accounts payable"

    again = rename(admin, "Accounts receivable")
    assert again.status_code == 200, again.text
    assert (
        members_of(owner).status_code == 200
        and owner.client.get("/api/auth/me").json()["orgs"][0]["name"]
        == "Accounts receivable"
    )


def test_a_member_does_not_rename_the_organization(new_account: NewAccount) -> None:
    owner = new_account()
    member = join(owner, new_account())

    refused = rename(member, "Not theirs")

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_an_admin"


def test_a_name_of_nothing_is_not_a_name(new_account: NewAccount) -> None:
    owner = new_account()

    refused = rename(owner, "   ")

    assert refused.status_code == 422, refused.text


def test_a_user_creates_a_further_organization_and_owns_it(
    new_account: NewAccount,
) -> None:
    owner = new_account()

    created = owner.client.post("/api/orgs", json={"name": "  Side project  "})

    assert created.status_code == 201, created.text
    made = created.json()
    assert made["name"] == "Side project"
    assert made["role"] == "owner"
    assert orgs_of(owner)[made["id"]] == "owner"
    assert roles_in(owner, made["id"]) == {user_id_of(owner): "owner"}
    acting = domain_work_in(owner, made["id"])
    assert acting.status_code == 404, acting.text
    assert acting.json()["code"] == "workflow_not_found"


def test_creating_an_organization_needs_a_session(new_account: NewAccount) -> None:
    owner = new_account()
    owner.client.post("/api/auth/logout")

    refused = owner.client.post("/api/orgs", json={"name": "Nobody's"})

    assert refused.status_code == 401, refused.text
    assert refused.json()["code"] == "unauthenticated"
