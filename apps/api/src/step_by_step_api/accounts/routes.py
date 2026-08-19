"""The accounts HTTP surface.

Every route here is under the one app origin, and every refusal is JSON with a
machine-readable code.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, StringConstraints

from step_by_step_api.accounts import (
    deletion,
    invitations,
    members,
    orgs,
    service,
    sessions,
)
from step_by_step_api.accounts.models import (
    Invitation,
    Membership,
    Organization,
    Role,
    User,
)
from step_by_step_api.accounts.orgs import (
    ManagingMembership,
    OwningMembership,
    PathMembership,
)
from step_by_step_api.accounts.service import SignupMode, signup_mode
from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import errors

Email = Annotated[
    str, Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
]
"""An address, checked only for the shape every address has.

Whether it can receive mail is the mail server's answer, not a regular
expression's, and the flow already waits for that answer: an address that
cannot receive the Sign-in Code never signs in.
"""

router = APIRouter()


class Instance(BaseModel):
    """What an unauthenticated visitor may learn about this instance."""

    signup_mode: SignupMode


@router.get("/api/instance", operation_id="getInstance")
def get_instance() -> Instance:
    """The one fact the sign-in screen needs before anyone has signed in."""
    return Instance(signup_mode=signup_mode())


class CodeRequest(BaseModel):
    """Step one of the sign-in screen: the address to send a code to."""

    email: Email


@router.post(
    "/api/auth/request-code",
    operation_id="requestSigninCode",
    status_code=202,
    response_class=Response,
    responses=errors(429),
)
def request_signin_code(asked: CodeRequest, db: SessionDep) -> Response:
    """Mail a Sign-in Code to an address — 202 whether or not it is anybody.

    The answer must not vary with whether an account exists, or it becomes a
    way to ask which addresses are on this instance. So there is nothing in
    the body to differ, and the caller learns what happened by entering a code.
    The issuance limit is the one refusal this route has, and it is about how
    often the caller has asked rather than about who the address is.
    """
    service.request_code(db, asked.email)
    db.commit()
    return Response(status_code=202)


class VerificationRequest(BaseModel):
    """Step two of the sign-in screen: the address, and the code it received."""

    email: Email
    code: str = Field(min_length=1, max_length=16)


class SignedIn(BaseModel):
    """What signing in tells the screen: whether this visit made the account.

    The screen needs it to decide between welcoming someone and letting them
    carry on, and it is the only thing that differs between the two.
    """

    created: bool


class OrganizationMembership(BaseModel):
    """One Organization a user acts in, and what they may do there."""

    id: UUID
    name: str
    role: Role


class OfferedMembership(BaseModel):
    """An Invitation as the person invited sees it: whose team, and as what."""

    id: UUID
    org_name: str
    role: Role


class Account(BaseModel):
    """Who the caller is. The email is theirs as they typed it."""

    id: UUID
    email: str
    display_name: str | None
    orgs: list[OrganizationMembership]
    invitations: list[OfferedMembership]


class AccountUpdate(BaseModel):
    """The one thing about an account its owner may change here."""

    display_name: str | None = Field(default=None, max_length=200)


def account_of(db: SessionDep, user: User) -> Account:
    """The account as every route that answers with one renders it."""
    return Account(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        orgs=[
            OrganizationMembership(id=org.id, name=org.name, role=role)
            for org, role in service.organizations_of(db, user)
        ],
        invitations=[
            OfferedMembership(
                id=invitation.id, org_name=organization.name, role=invitation.role
            )
            for invitation, organization in invitations.pending_for(db, user.email)
        ],
    )


@router.post(
    "/api/auth/verify-code",
    operation_id="verifySigninCode",
    responses=errors(401, 403, 429),
)
def verify_signin_code(
    asked: VerificationRequest, request: Request, response: Response, db: SessionDep
) -> SignedIn:
    """Prove control of an address, which signs in — and signs up if it is new."""
    verified = service.verify_code(db, asked.email, asked.code)
    if verified.user is None:
        # Committed before the refusal on purpose: a wrong guess counted
        # against the code, and a code spent on a closed instance, are both
        # facts that must survive the answer that carries them.
        db.commit()
        raise service.refusal(verified.verdict)
    sessions.carry(request, response, sessions.begin(db, verified.user))
    db.commit()
    return SignedIn(created=verified.created)


@router.get("/api/auth/me", operation_id="getCurrentAccount", responses=errors(401))
def get_current_account(user: CurrentUser, db: SessionDep) -> Account:
    """Who the caller is, and which Organizations they can act in."""
    return account_of(db, user)


@router.patch("/api/account", operation_id="updateAccount", responses=errors(401))
def update_account(change: AccountUpdate, user: CurrentUser, db: SessionDep) -> Account:
    """Change the display name. The email is the identity and is not editable."""
    user.display_name = change.display_name
    db.commit()
    return account_of(db, user)


class AccountDeletion(BaseModel):
    """The account's own address, typed by the person ending it."""

    email_confirmation: str = Field(max_length=320)


@router.delete(
    "/api/account",
    operation_id="deleteAccount",
    status_code=204,
    response_class=Response,
    responses=errors(400, 401, 403),
)
def delete_account(
    asked: AccountDeletion, user: CurrentUser, db: SessionDep
) -> Response:
    """End this account, behind typing its address — hard, and for good.

    Every session goes with it, so the browser asking is signed out by the
    answer it gets, and the cookie it still carries is taken back here. An
    account that owns an Organization is refused: leaving must not leave a
    team with nobody who can act for it.
    """
    deletion.end_account(db, user, asked.email_confirmation)
    db.commit()
    answer = Response(status_code=204)
    sessions.drop(answer)
    return answer


@router.post(
    "/api/auth/logout",
    operation_id="signOut",
    status_code=204,
    response_class=Response,
    responses=errors(401),
)
def sign_out(request: Request, user: CurrentUser, db: SessionDep) -> Response:
    """End this session — the row goes, and the browser stops carrying its key.

    Other sessions of the same user are untouched; `logout-all` is the one
    that reaches them.
    """
    token = request.cookies.get(sessions.SESSION_COOKIE, "")
    sessions.end(db, token)
    db.commit()
    answer = Response(status_code=204)
    sessions.drop(answer)
    return answer


@router.post(
    "/api/auth/logout-all",
    operation_id="signOutEverywhere",
    status_code=204,
    response_class=Response,
    responses=errors(401),
)
def sign_out_everywhere(user: CurrentUser, db: SessionDep) -> Response:
    """End every session this account has, this one included.

    The action for a browser the person no longer has — a phone left in a taxi,
    a machine at an old job — so it deliberately reaches the sessions this
    request cannot see, and takes the asking one with them.
    """
    sessions.end_all(db, user)
    db.commit()
    answer = Response(status_code=204)
    sessions.drop(answer)
    return answer


class AssignableRole(StrEnum):
    """The two roles a Membership may be given.

    Not owner: an Organization has exactly one, and it changes hands by the
    transfer that replaces its holder — never by an offer somebody might never
    take up, and never by a role change that would leave two.
    """

    ADMIN = "admin"
    MEMBER = "member"


class InvitationRequest(BaseModel):
    """An offer to make: the address, and what it may do once it is taken."""

    email: Email
    role: AssignableRole


class PendingInvitation(BaseModel):
    """An offer an Organization has out, as its owner and admins see it."""

    id: UUID
    email: str
    role: Role
    created_at: datetime
    expires_at: datetime


def pending(invitation: Invitation) -> PendingInvitation:
    """The Invitation as every route that answers with one renders it."""
    return PendingInvitation(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
    )


@router.get(
    "/api/orgs/{org_id}/invitations",
    operation_id="listInvitations",
    responses=errors(401, 403),
)
def list_invitations(
    org_id: UUID, managing: ManagingMembership, db: SessionDep
) -> list[PendingInvitation]:
    """The offers this Organization has standing — never the spent ones.

    An Invitation that was accepted, revoked, or has run out is not a thing
    anyone can act on, so it is not on a list whose every row has actions.
    """
    return [pending(invitation) for invitation in invitations.pending_in(db, org_id)]


@router.post(
    "/api/orgs/{org_id}/invitations",
    operation_id="createInvitation",
    status_code=201,
    responses=errors(401, 403, 409),
)
def create_invitation(
    org_id: UUID, asked: InvitationRequest, managing: ManagingMembership, db: SessionDep
) -> PendingInvitation:
    """Invite an address into this Organization, and mail it the offer."""
    organization = db.get_one(Organization, org_id)
    invitation = invitations.offer(db, organization, asked.email, Role(asked.role))
    db.commit()
    return pending(invitation)


@router.delete(
    "/api/orgs/{org_id}/invitations/{invitation_id}",
    operation_id="revokeInvitation",
    status_code=204,
    response_class=Response,
    responses=errors(401, 403, 404),
)
def revoke_invitation(
    org_id: UUID,
    invitation_id: UUID,
    managing: ManagingMembership,
    db: SessionDep,
) -> Response:
    """Withdraw an offer: the invitee stops seeing it and cannot take it up."""
    invitations.revoke(db, org_id, invitation_id)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/api/invitations/{invitation_id}/accept",
    operation_id="acceptInvitation",
    status_code=204,
    response_class=Response,
    responses=errors(401, 404),
)
def accept_invitation(
    invitation_id: UUID, user: CurrentUser, db: SessionDep
) -> Response:
    """Take up an offer made to this account's address, which joins the team.

    Being signed in as the invited address is the whole of the proof, because
    signing in is proof of the address the offer was made to.
    """
    invitations.accept(db, user, invitation_id)
    db.commit()
    return Response(status_code=204)


class OrganizationRequest(BaseModel):
    """What an Organization is made and renamed with: a name people read."""

    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]


@router.post(
    "/api/orgs",
    operation_id="createOrganization",
    status_code=201,
    responses=errors(401),
)
def create_organization(
    asked: OrganizationRequest, user: CurrentUser, db: SessionDep
) -> OrganizationMembership:
    """Start a further Organization, owned by whoever asked for it.

    Signing up makes the first one; this is every one after it — a second team,
    a client's work kept apart from another's — and it answers with the same
    shape the current-user view lists, because that is where it turns up next.
    """
    organization = orgs.create(db, user, asked.name)
    db.commit()
    return OrganizationMembership(
        id=organization.id, name=organization.name, role=Role.OWNER
    )


class OrganizationDeletion(BaseModel):
    """The Organization's own name, typed by the owner who is ending it."""

    name_confirmation: str = Field(max_length=200)


@router.delete(
    "/api/orgs/{org_id}",
    operation_id="deleteOrganization",
    status_code=204,
    response_class=Response,
    responses=errors(400, 401, 403),
)
def delete_organization(
    org_id: UUID,
    asked: OrganizationDeletion,
    owner: OwningMembership,
    db: SessionDep,
) -> Response:
    """End the Organization, and everything that belonged to it.

    The owner's alone, and behind typing the name: the Memberships, the
    Invitations, and every piece of work the Organization owns go with it, and
    nothing brings them back. Its people keep their accounts and their other
    Organizations — what ends is the team, not the members.
    """
    deletion.end_organization(
        db, db.get_one(Organization, org_id), asked.name_confirmation
    )
    db.commit()
    return Response(status_code=204)


@router.patch(
    "/api/orgs/{org_id}",
    operation_id="renameOrganization",
    responses=errors(401, 403),
)
def rename_organization(
    org_id: UUID,
    asked: OrganizationRequest,
    managing: ManagingMembership,
    db: SessionDep,
) -> OrganizationMembership:
    """Rename the Organization, which an owner and the admins may both do.

    The name a signup made is the local part of an address, so the first thing
    a team does with an Organization is give it their own name for it.
    """
    organization = db.get_one(Organization, org_id)
    organization.name = asked.name
    db.commit()
    return OrganizationMembership(
        id=organization.id, name=organization.name, role=managing.role
    )


class Member(BaseModel):
    """One person in an Organization, as its members screen shows them."""

    user_id: UUID
    email: str
    display_name: str | None
    role: Role
    joined_at: datetime


class RoleChange(BaseModel):
    """The one thing about a Membership that changes: what it lets them do."""

    role: AssignableRole


class OwnershipTransfer(BaseModel):
    """Who the Organization is being handed to."""

    user_id: UUID


def rendered(membership: Membership, user: User) -> Member:
    """The Membership as every route that answers with one renders it."""
    return Member(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        joined_at=membership.created_at,
    )


@router.get(
    "/api/orgs/{org_id}/members",
    operation_id="listMembers",
    responses=errors(401, 403),
)
def list_members(
    org_id: UUID, membership: PathMembership, db: SessionDep
) -> list[Member]:
    """Who else is here — a question every role in an Organization may ask.

    Knowing who you work with is not managing them: the roles that gate this
    screen's controls do not gate the screen.
    """
    return [rendered(member, user) for member, user in members.listing(db, org_id)]


@router.patch(
    "/api/orgs/{org_id}/members/{user_id}",
    operation_id="changeMemberRole",
    responses=errors(401, 403, 404),
)
def change_member_role(
    org_id: UUID,
    user_id: UUID,
    asked: RoleChange,
    managing: ManagingMembership,
    db: SessionDep,
) -> Member:
    """Move somebody between member and admin, which owners and admins both do."""
    membership = members.set_role(db, org_id, user_id, Role(asked.role))
    user = db.get_one(User, user_id)
    db.commit()
    return rendered(membership, user)


@router.delete(
    "/api/orgs/{org_id}/members/{user_id}",
    operation_id="removeMember",
    status_code=204,
    response_class=Response,
    responses=errors(401, 403, 404),
)
def remove_member(
    org_id: UUID, user_id: UUID, membership: PathMembership, db: SessionDep
) -> Response:
    """End a Membership — an owner's or an admin's removal, or anyone's leaving.

    Access ends with the row: the next request naming this Organization has no
    Membership behind it, and the gate refuses it. The session is untouched,
    because it is the account's and not this Organization's.
    """
    members.remove(db, membership, user_id)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/api/orgs/{org_id}/transfer-ownership",
    operation_id="transferOwnership",
    status_code=204,
    response_class=Response,
    responses=errors(401, 403, 404),
)
def transfer_ownership(
    org_id: UUID, asked: OwnershipTransfer, owner: OwningMembership, db: SessionDep
) -> Response:
    """Hand the Organization to another of its members, and stay on as an admin."""
    members.transfer_ownership(db, owner, asked.user_id)
    db.commit()
    return Response(status_code=204)
