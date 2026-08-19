"""Invitations: how a team forms.

An owner or admin offers an address a place in their Organization with a role,
the offer goes out through the mailer seam, and signing in with that address
and accepting it creates the Membership. Nothing else joins anyone to an
Organization (ADR 0005): there is no instance administrator to add people, and
no link that signs a visitor in.

The offer is made to an *address*, not to an account, which is what lets an
Organization invite someone who has never been here — and, under
`SIGNUP_MODE=invite_only`, what serves as their permit to have an account at
all.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock, mail
from step_by_step_api.accounts.models import (
    Invitation,
    Membership,
    Organization,
    Role,
    User,
)
from step_by_step_api.errors import ApiError

INVITATION_LIFETIME = timedelta(days=14)
"""How long an offer stands. After it, the row is there and the offer is not."""


def normalized(email: str) -> str:
    """The form an address is compared by — identity is case-insensitive."""
    return email.strip().lower()


def pending_in(db: DbSession, org_id: UUID) -> list[Invitation]:
    """The offers an Organization has out: not expired, not revoked."""
    return list(
        db.execute(
            select(Invitation)
            .where(Invitation.org_id == org_id, Invitation.expires_at > clock.now())
            .order_by(Invitation.created_at)
        )
        .scalars()
        .all()
    )


def pending_for(db: DbSession, email: str) -> list[tuple[Invitation, Organization]]:
    """The offers standing for an address, with the Organization each is into.

    Revoking deletes the row, so an offer that is gone is gone from here too:
    this is the one place a signed-in user learns they were invited, and it
    must not show them a door that has already been closed.
    """
    rows = db.execute(
        select(Invitation, Organization)
        .join(Organization, Organization.id == Invitation.org_id)
        .where(
            func.lower(Invitation.email) == normalized(email),
            Invitation.expires_at > clock.now(),
        )
        .order_by(Invitation.created_at)
    ).all()
    return [(invitation, organization) for invitation, organization in rows]


def offer(
    db: DbSession, organization: Organization, email: str, role: Role
) -> Invitation:
    """Invite an address into an Organization, and mail it the offer.

    Two refusals, and both are about the same address rather than about the
    same string: someone who is already a member has nothing to accept, and a
    second standing offer would be a second row for one decision — whichever
    of the two they accepted, the other would outlive it.
    """
    address = normalized(email)
    if member_by_email(db, organization.id, address) is not None:
        raise ApiError(
            409, "already_member", "that address is already in this Organization"
        )
    if any(
        normalized(standing.email) == address
        for standing in pending_in(db, organization.id)
    ):
        raise ApiError(
            409, "already_invited", "that address already has an Invitation standing"
        )
    invitation = Invitation(
        org_id=organization.id,
        email=email.strip(),
        role=role,
        expires_at=clock.now() + INVITATION_LIFETIME,
    )
    db.add(invitation)
    db.flush()
    mail.send(
        to=invitation.email,
        subject=f"You have been invited to {organization.name} on Step by Step",
        text=invitation_email(organization.name, role),
    )
    return invitation


def invitation_email(org_name: str, role: Role) -> str:
    """The second and last email this product sends.

    It carries no link: signing in is a Sign-in Code sent to this same address,
    so a link here would be a second way in and no faster than the first.
    """
    return (
        f"You have been invited to join {org_name} on Step by Step "
        f"as {'an' if role is Role.ADMIN else 'a'} {role}.\n\n"
        "Sign in with this email address to accept the invitation. "
        "It expires in 14 days.\n"
        "If you were not expecting it, you can ignore this email."
    )


def member_by_email(db: DbSession, org_id: UUID, email: str) -> Membership | None:
    """The Membership an address holds in an Organization, if it holds one."""
    return db.execute(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id, func.lower(User.email) == normalized(email))
    ).scalar_one_or_none()


def revoke(db: DbSession, org_id: UUID, invitation_id: UUID) -> None:
    """Withdraw an offer this Organization made, which is deleting its row."""
    invitation = db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.org_id == org_id
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise unknown_invitation()
    db.delete(invitation)


def accept(db: DbSession, user: User, invitation_id: UUID) -> None:
    """Take up an offer made to this user's address, which joins them.

    The row is locked and then deleted, so that two accepts of one offer make
    one Membership: the second finds nothing and answers as it would for an
    offer that was never made.

    An offer to another address is not this user's to accept, and it answers
    404 rather than 403 — an id someone else holds is not a fact they may
    confirm by guessing at it.

    Accepting an offer you have already taken up is spending it, not an error:
    `offer()` refuses a second standing Invitation by reading first, so two
    admins inviting one address in the same instant can leave two rows for one
    decision, and the second is a Membership this user already holds. It goes,
    and the role of the offer that was accepted stands.
    """
    invitation = db.execute(
        select(Invitation).where(Invitation.id == invitation_id).with_for_update()
    ).scalar_one_or_none()
    if (
        invitation is None
        or normalized(invitation.email) != normalized(user.email)
        or invitation.expires_at <= clock.now()
    ):
        raise unknown_invitation()
    db.delete(invitation)
    if member_by_email(db, invitation.org_id, user.email) is not None:
        return
    db.add(Membership(org_id=invitation.org_id, user_id=user.id, role=invitation.role))


def unknown_invitation() -> ApiError:
    """The one answer for revoked, expired, taken, and never made."""
    return ApiError(404, "invitation_not_found", "no such Invitation")
