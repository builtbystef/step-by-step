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


def normalized(email: str) -> str:
    return email.strip().lower()


def pending_in(db: DbSession, org_id: UUID) -> list[Invitation]:
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
    return (
        f"You have been invited to join {org_name} on Step by Step "
        f"as {'an' if role is Role.ADMIN else 'a'} {role}.\n\n"
        "Sign in with this email address to accept the invitation. "
        "It expires in 14 days.\n"
        "If you were not expecting it, you can ignore this email."
    )


def member_by_email(db: DbSession, org_id: UUID, email: str) -> Membership | None:
    return db.execute(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id, func.lower(User.email) == normalized(email))
    ).scalar_one_or_none()


def revoke(db: DbSession, org_id: UUID, invitation_id: UUID) -> None:
    invitation = db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.org_id == org_id
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise unknown_invitation()
    db.delete(invitation)


def accept(db: DbSession, user: User, invitation_id: UUID) -> None:
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
    return ApiError(404, "invitation_not_found", "no such Invitation")
