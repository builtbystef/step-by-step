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
from step_by_step_api.accounts.service import SignupMode, default_timezone, signup_mode
from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import errors

Email = Annotated[
    str, Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
]

router = APIRouter()


class Instance(BaseModel):
    signup_mode: SignupMode
    default_timezone: str


@router.get("/api/instance", operation_id="getInstance")
def get_instance() -> Instance:
    return Instance(signup_mode=signup_mode(), default_timezone=default_timezone())


class CodeRequest(BaseModel):
    email: Email


@router.post(
    "/api/auth/request-code",
    operation_id="requestSigninCode",
    status_code=202,
    response_class=Response,
    responses=errors(429),
)
def request_signin_code(asked: CodeRequest, db: SessionDep) -> Response:
    service.request_code(db, asked.email)
    db.commit()
    return Response(status_code=202)


class VerificationRequest(BaseModel):
    email: Email
    code: str = Field(min_length=1, max_length=16)


class SignedIn(BaseModel):
    created: bool


class OrganizationMembership(BaseModel):
    id: UUID
    name: str
    role: Role


class OfferedMembership(BaseModel):
    id: UUID
    org_name: str
    role: Role


class Account(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    orgs: list[OrganizationMembership]
    invitations: list[OfferedMembership]


class AccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)


def account_of(db: SessionDep, user: User) -> Account:
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
    verified = service.verify_code(db, asked.email, asked.code)
    if verified.user is None:
        # Persist consumed attempts even though the request is refused.
        db.commit()
        raise service.refusal(verified.verdict)
    sessions.carry(request, response, sessions.begin(db, verified.user))
    db.commit()
    return SignedIn(created=verified.created)


@router.get("/api/auth/me", operation_id="getCurrentAccount", responses=errors(401))
def get_current_account(user: CurrentUser, db: SessionDep) -> Account:
    return account_of(db, user)


@router.patch("/api/account", operation_id="updateAccount", responses=errors(401))
def update_account(change: AccountUpdate, user: CurrentUser, db: SessionDep) -> Account:
    user.display_name = change.display_name
    db.commit()
    return account_of(db, user)


class AccountDeletion(BaseModel):
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
    sessions.end_all(db, user)
    db.commit()
    answer = Response(status_code=204)
    sessions.drop(answer)
    return answer


class AssignableRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class InvitationRequest(BaseModel):
    email: Email
    role: AssignableRole


class PendingInvitation(BaseModel):
    id: UUID
    email: str
    role: Role
    created_at: datetime
    expires_at: datetime


def pending(invitation: Invitation) -> PendingInvitation:
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
    invitations.accept(db, user, invitation_id)
    db.commit()
    return Response(status_code=204)


class OrganizationRequest(BaseModel):
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
    organization = orgs.create(db, user, asked.name)
    db.commit()
    return OrganizationMembership(
        id=organization.id, name=organization.name, role=Role.OWNER
    )


class OrganizationDeletion(BaseModel):
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
    organization = db.get_one(Organization, org_id)
    organization.name = asked.name
    db.commit()
    return OrganizationMembership(
        id=organization.id, name=organization.name, role=managing.role
    )


class Member(BaseModel):
    user_id: UUID
    email: str
    display_name: str | None
    role: Role
    joined_at: datetime


class RoleChange(BaseModel):
    role: AssignableRole


class OwnershipTransfer(BaseModel):
    user_id: UUID


def rendered(membership: Membership, user: User) -> Member:
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
    members.transfer_ownership(db, owner, asked.user_id)
    db.commit()
    return Response(status_code=204)
