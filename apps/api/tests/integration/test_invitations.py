from collections.abc import Callable
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from conftest import Account, code_sent_to, join
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session
from step_by_step_api import clock
from step_by_step_api.accounts.models import Invitation
from step_by_step_api.accounts.service import SIGNUP_MODE_VARIABLE
from step_by_step_api.db import get_engine
from step_by_step_api.mail import outbox
from step_by_step_api.main import app

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


def invite(inviter: Account, email: str, role: str = "member") -> Response:
    return inviter.client.post(
        f"/api/orgs/{inviter.org_id}/invitations", json={"email": email, "role": role}
    )


def mail_to(address: str) -> str:
    for message in reversed(outbox()):
        if message.to == address:
            return f"{message.subject}\n{message.text}"
    raise AssertionError(f"no mail was sent to {address}")


def test_an_owner_invites_an_address_and_the_invitation_is_emailed(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    invited = "grace@example.com"

    offered = invite(owner, invited, role="admin")

    assert offered.status_code == 201, offered.text
    assert offered.json()["email"] == invited
    assert offered.json()["role"] == "admin"
    assert owner.email.split("@")[0] in mail_to(invited)


def offered_to(account: Account) -> list[dict[str, object]]:
    me = account.client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    offers: list[dict[str, object]] = me.json()["invitations"]
    return offers


def organizations_of(account: Account) -> list[tuple[str, str]]:
    me = account.client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return [(org["id"], org["role"]) for org in me.json()["orgs"]]


def test_the_invited_address_sees_the_offer_whatever_case_it_was_written_in(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    invitee = new_account()

    assert invite(owner, invitee.email.upper(), role="admin").status_code == 201

    offers = offered_to(invitee)
    assert [(offer["org_name"], offer["role"]) for offer in offers] == [
        (owner.email.split("@")[0], "admin")
    ]


def test_accepting_an_invitation_joins_the_organization_with_its_role(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    invitee = new_account()
    invite(owner, invitee.email)
    offer_id = offered_to(invitee)[0]["id"]

    accepted = invitee.client.post(f"/api/invitations/{offer_id}/accept")

    assert accepted.status_code == 204, accepted.text
    assert (owner.org_id, "member") in organizations_of(invitee)
    assert offered_to(invitee) == []


def test_an_invitation_is_not_another_accounts_to_accept(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    invitee = new_account()
    invite(owner, invitee.email)
    offer_id = offered_to(invitee)[0]["id"]
    stranger = new_account()

    refused = stranger.client.post(f"/api/invitations/{offer_id}/accept")

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "invitation_not_found"
    assert offered_to(invitee) != []


def an_address() -> str:
    return f"grace-{uuid4().hex[:12]}@example.com"


def test_an_admin_invites_and_a_member_may_not(new_account: NewAccount) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")
    member = join(owner, new_account(), role="member")

    invited = invite(admin, an_address())
    refused = invite(member, an_address())

    assert invited.status_code == 201, invited.text
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_an_admin"


def test_inviting_into_an_organization_you_are_not_in_is_refused(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    stranger = Account(
        client=new_account().client, email="nobody@example.com", org_id=owner.org_id
    )

    refused = invite(stranger, an_address())

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_a_member"


def test_inviting_needs_a_session(new_account: NewAccount) -> None:
    owner = new_account()
    owner.client.post("/api/auth/logout")

    refused = invite(owner, an_address())

    assert refused.status_code == 401, refused.text
    assert refused.json()["code"] == "unauthenticated"


def test_an_address_already_in_the_organization_cannot_be_invited(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account(), role="member")

    refused = invite(owner, member.email.upper())

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "already_member"


def test_a_second_standing_invitation_for_one_address_is_refused(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    address = an_address()
    assert invite(owner, address).status_code == 201

    again = invite(owner, address.upper(), role="admin")

    assert again.status_code == 409, again.text
    assert again.json()["code"] == "already_invited"
    assert len(pending_in(owner)) == 1


def pending_in(managing: Account) -> list[dict[str, object]]:
    listed = managing.client.get(f"/api/orgs/{managing.org_id}/invitations")
    assert listed.status_code == 200, listed.text
    invitations: list[dict[str, object]] = listed.json()
    return invitations


def test_owners_and_admins_list_the_standing_invitations(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    admin = join(owner, new_account(), role="admin")
    member = join(owner, new_account(), role="member")
    address = an_address()
    invite(owner, address, role="admin")

    assert [(offer["email"], offer["role"]) for offer in pending_in(owner)] == [
        (address, "admin")
    ]
    assert pending_in(admin) == pending_in(owner)
    refused = member.client.get(f"/api/orgs/{member.org_id}/invitations")
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_an_admin"


def test_a_revoked_invitation_is_gone_for_both_sides(new_account: NewAccount) -> None:
    owner = new_account()
    invitee = new_account()
    invite(owner, invitee.email)
    offer_id = offered_to(invitee)[0]["id"]

    revoked = owner.client.delete(f"/api/orgs/{owner.org_id}/invitations/{offer_id}")

    assert revoked.status_code == 204, revoked.text
    assert revoked.content == b""
    assert pending_in(owner) == []
    assert offered_to(invitee) == []
    taken = invitee.client.post(f"/api/invitations/{offer_id}/accept")
    assert taken.status_code == 404
    assert taken.json()["code"] == "invitation_not_found"


def test_only_the_inviting_organization_revokes_its_invitation(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    address = an_address()
    offer_id = invite(owner, address).json()["id"]
    elsewhere = new_account()

    refused = elsewhere.client.delete(
        f"/api/orgs/{elsewhere.org_id}/invitations/{offer_id}"
    )

    assert refused.status_code == 404, refused.text
    assert len(pending_in(owner)) == 1


def raced_duplicate_of(offer: dict[str, object]) -> str:
    with Session(get_engine()) as db:
        first = db.get_one(Invitation, UUID(str(offer["id"])))
        second = Invitation(
            org_id=first.org_id,
            email=first.email,
            role=first.role,
            expires_at=first.expires_at,
        )
        db.add(second)
        db.commit()
        return str(second.id)


def test_accepting_a_second_invitation_you_have_already_taken_up_changes_nothing(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    invitee = new_account()
    offered = invite(owner, invitee.email, role="member")
    duplicate_id = raced_duplicate_of(offered.json())
    first_id = offered.json()["id"]
    assert invitee.client.post(f"/api/invitations/{first_id}/accept").status_code == 204

    again = invitee.client.post(f"/api/invitations/{duplicate_id}/accept")

    assert again.status_code == 204, again.text
    assert organizations_of(invitee).count((owner.org_id, "member")) == 1
    assert offered_to(invitee) == []
    assert pending_in(owner) == []


def test_an_invitation_older_than_fourteen_days_is_no_longer_an_offer(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = new_account()
    invitee = new_account()
    invite(owner, invitee.email)
    offer_id = offered_to(invitee)[0]["id"]
    later = clock.now() + timedelta(days=14, seconds=1)
    monkeypatch.setattr(clock, "now", lambda: later)

    taken = invitee.client.post(f"/api/invitations/{offer_id}/accept")

    assert taken.status_code == 404, taken.text
    assert taken.json()["code"] == "invitation_not_found"
    assert offered_to(invitee) == []
    assert pending_in(owner) == []


def test_an_invitation_is_the_signup_permit_on_an_invite_only_instance(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = new_account()
    invited = an_address()
    invite(owner, invited, role="admin")
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite_only")

    visitor = TestClient(app)
    assert (
        visitor.post("/api/auth/request-code", json={"email": invited}).status_code
        == 202
    )
    signed_up = visitor.post(
        "/api/auth/verify-code",
        json={"email": invited, "code": code_sent_to(invited)},
    )

    assert signed_up.status_code == 200, signed_up.text
    assert signed_up.json() == {"created": True}
    account = visitor.get("/api/auth/me").json()
    assert account["orgs"] == []
    assert [offer["org_name"] for offer in account["invitations"]] == [
        owner.email.split("@")[0]
    ]

    accepted = visitor.post(
        f"/api/invitations/{account['invitations'][0]['id']}/accept"
    )

    assert accepted.status_code == 204, accepted.text
    assert [
        (org["id"], org["role"]) for org in visitor.get("/api/auth/me").json()["orgs"]
    ] == [(owner.org_id, "admin")]


def test_an_uninvited_address_still_meets_a_closed_instance(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = new_account()
    invite(owner, an_address())
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite_only")

    visitor = TestClient(app)
    uninvited = an_address()
    visitor.post("/api/auth/request-code", json={"email": uninvited})
    refused = visitor.post(
        "/api/auth/verify-code",
        json={"email": uninvited, "code": code_sent_to(uninvited)},
    )

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "signup_closed"
