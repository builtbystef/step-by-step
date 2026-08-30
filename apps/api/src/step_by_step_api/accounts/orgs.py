from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select

from step_by_step_api.accounts.models import Membership, Organization, Role, User
from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError

ORGANIZATION_HEADER = "X-Organization"


def active_membership(
    db: SessionDep,
    user: CurrentUser,
    organization: Annotated[str | None, Header(alias=ORGANIZATION_HEADER)] = None,
) -> Membership:
    if organization is None:
        raise ApiError(
            400, "organization_required", f"{ORGANIZATION_HEADER} names no Organization"
        )
    try:
        org_id = UUID(organization)
    except ValueError:
        raise no_membership() from None
    membership = membership_in(db, user, org_id)
    if membership is None:
        raise no_membership()
    return membership


def membership_in(db: SessionDep, user: User, org_id: UUID) -> Membership | None:
    return db.execute(
        select(Membership).where(
            Membership.org_id == org_id, Membership.user_id == user.id
        )
    ).scalar_one_or_none()


def path_membership(db: SessionDep, user: CurrentUser, org_id: UUID) -> Membership:
    membership = membership_in(db, user, org_id)
    if membership is None:
        raise no_membership()
    return membership


def managing_membership(db: SessionDep, user: CurrentUser, org_id: UUID) -> Membership:
    membership = path_membership(db, user, org_id)
    if membership.role is Role.MEMBER:
        raise not_an_admin()
    return membership


def owning_membership(db: SessionDep, user: CurrentUser, org_id: UUID) -> Membership:
    membership = path_membership(db, user, org_id)
    if membership.role is not Role.OWNER:
        raise not_the_owner()
    return membership


def create(db: SessionDep, user: User, name: str) -> Organization:
    organization = Organization(name=name)
    db.add(organization)
    db.flush()
    db.add(Membership(org_id=organization.id, user_id=user.id, role=Role.OWNER))
    return organization


def not_the_owner() -> ApiError:
    return ApiError(403, "not_the_owner", "only the owner may do that")


def no_membership() -> ApiError:
    return ApiError(403, "not_a_member", "you are not a member of that Organization")


def not_an_admin() -> ApiError:
    return ApiError(403, "not_an_admin", "only an owner or an admin may manage this")


ActiveMembership = Annotated[Membership, Depends(active_membership)]

PathMembership = Annotated[Membership, Depends(path_membership)]

ManagingMembership = Annotated[Membership, Depends(managing_membership)]

OwningMembership = Annotated[Membership, Depends(owning_membership)]
