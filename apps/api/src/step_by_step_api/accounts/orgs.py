"""Which Organization a request is acting in, and what its role lets it do.

Domain routes keep flat paths (`/api/workflows`, …) and carry the acting
Organization in a header, so that no path has to grow a tenant segment. The
header names it; the caller's Membership in it is what authorizes the request,
and it is checked on every one (ADR 0005).

The Organization's own routes name it in the path instead, because they are
about one Organization rather than acting inside the active one — and there
the Membership has to carry a role as well, so the gate comes in three widths.
Being in an Organization is enough to read who else is in it and to leave;
managing who is in a team is the owner's and the admins'; handing the
Organization on is the owner's alone. The work itself is every role's.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select

from step_by_step_api.accounts.models import Membership, Organization, Role, User
from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError

ORGANIZATION_HEADER = "X-Organization"
"""The header the frontend's fetch wrapper sets from the active Organization."""


def active_membership(
    db: SessionDep,
    user: CurrentUser,
    organization: Annotated[str | None, Header(alias=ORGANIZATION_HEADER)] = None,
) -> Membership:
    """The caller's Membership in the Organization they say they are acting in.

    An id that is not a UUID answers the same as an id nobody is a member of:
    the caller has no Membership in what they named, and which of the two it
    was is not a client's business — it would say which ids exist.
    """
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
    """The place a user holds in one Organization, if they hold one at all."""
    return db.execute(
        select(Membership).where(
            Membership.org_id == org_id, Membership.user_id == user.id
        )
    ).scalar_one_or_none()


def path_membership(db: SessionDep, user: CurrentUser, org_id: UUID) -> Membership:
    """The caller's Membership in the Organization a path names, any role.

    What every role may do in an Organization it belongs to: reading who else
    is in it, and leaving.
    """
    membership = membership_in(db, user, org_id)
    if membership is None:
        raise no_membership()
    return membership


def managing_membership(db: SessionDep, user: CurrentUser, org_id: UUID) -> Membership:
    """The caller's Membership in the Organization a path names, with a role
    that lets them manage who is in it.

    A member is told they are not an admin rather than that they are not a
    member: they are in this Organization, and hiding that from them would be
    hiding a fact they already hold.
    """
    membership = path_membership(db, user, org_id)
    if membership.role is Role.MEMBER:
        raise not_an_admin()
    return membership


def owning_membership(db: SessionDep, user: CurrentUser, org_id: UUID) -> Membership:
    """The caller's Membership in the Organization a path names, and it is theirs.

    The narrowest gate there is, for the two acts an Organization has exactly
    one person for: handing it on, and — with a later slice — ending it.
    """
    membership = path_membership(db, user, org_id)
    if membership.role is not Role.OWNER:
        raise not_the_owner()
    return membership


def create(db: SessionDep, user: User, name: str) -> Organization:
    """A new Organization, with the person who asked for it as its owner.

    The one way an Organization comes into being besides a signup's — and it is
    the same way: whoever makes one owns it, because an Organization with no
    owner would be one nobody could hand on or end.
    """
    organization = Organization(name=name)
    db.add(organization)
    db.flush()
    db.add(Membership(org_id=organization.id, user_id=user.id, role=Role.OWNER))
    return organization


def not_the_owner() -> ApiError:
    """The refusal on the acts an Organization has exactly one person for."""
    return ApiError(403, "not_the_owner", "only the owner may do that")


def no_membership() -> ApiError:
    """The one refusal for acting in an Organization the caller is not in."""
    return ApiError(403, "not_a_member", "you are not a member of that Organization")


def not_an_admin() -> ApiError:
    """The refusal a member meets on the controls that manage a team."""
    return ApiError(403, "not_an_admin", "only an owner or an admin may manage this")


ActiveMembership = Annotated[Membership, Depends(active_membership)]
"""A route parameter of this type is a route that acts inside one Organization."""

PathMembership = Annotated[Membership, Depends(path_membership)]
"""A route parameter of this type is every member's, on a path that names its
Organization as `{org_id}`."""

ManagingMembership = Annotated[Membership, Depends(managing_membership)]
"""A route parameter of this type is an owner's and an admin's, on a path that
names its Organization as `{org_id}`."""

OwningMembership = Annotated[Membership, Depends(owning_membership)]
"""A route parameter of this type is the owner's alone, on a path that names
its Organization as `{org_id}`."""
