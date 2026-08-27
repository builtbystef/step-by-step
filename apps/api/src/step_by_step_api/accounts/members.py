"""Who is in an Organization, and everything that changes it after joining.

Joining is the Invitations module's; this is the life afterwards. Every role
reads the member list, an owner and the admins change roles between member and
admin and remove people, anybody but the owner leaves, and the owner hands the
Organization on — which is the only way its one owner changes.

The owner is the invariant: exactly one per Organization, never removable, and
never demoted except by the transfer that replaces them. Every refusal that
protects it is the same one, `is_owner`, because from a caller's side it is
one fact — that Membership is not yours to end or to rewrite.

A Membership ending ends access at once, and nothing else: the gate in
`orgs.py` reads the row on every request, so there is no session to revoke and
no cache to clear. The Organization's own work — its Schedules, its Runs —
belongs to the Organization rather than to whoever left. Deleting the leaver's
Personal Overrides waits for the vault that holds them.
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api.accounts.models import Membership, Role, User
from step_by_step_api.accounts.orgs import not_an_admin, not_the_owner
from step_by_step_api.errors import ApiError
from step_by_step_api.secrets.models import Secret, SecretOverride


def listing(db: DbSession, org_id: UUID) -> list[tuple[Membership, User]]:
    """Everybody in the Organization, oldest Membership first.

    In join order rather than by role or by name: it is the one order that
    does not move under a screen when somebody is promoted.
    """
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id)
        .order_by(Membership.created_at, User.email)
    ).all()
    return [(membership, user) for membership, user in rows]


def member(db: DbSession, org_id: UUID, user_id: UUID) -> Membership:
    """The Membership a route names, or the refusal that it names none.

    404 rather than 403: a user id that is in no Organization of the caller's
    is not a thing they may confirm the existence of.
    """
    membership = db.execute(
        select(Membership).where(
            Membership.org_id == org_id, Membership.user_id == user_id
        )
    ).scalar_one_or_none()
    if membership is None:
        raise unknown_member()
    return membership


def set_role(db: DbSession, org_id: UUID, user_id: UUID, role: Role) -> Membership:
    """Move somebody between member and admin."""
    membership = member(db, org_id, user_id)
    if membership.role is Role.OWNER:
        raise is_owner()
    membership.role = role
    return membership


def remove(db: DbSession, caller: Membership, user_id: UUID) -> None:
    """End a Membership: somebody else's, or — the same act — the caller's own.

    Leaving and being removed are one route because they are one outcome, and
    the difference between them is only who asked. What separates them is the
    role: a member may end their own Membership and nobody else's, which is
    why the gate on this route is every member's and the check is here.
    """
    if user_id != caller.user_id and caller.role is Role.MEMBER:
        raise not_an_admin()
    membership = member(db, caller.org_id, user_id)
    if membership.role is Role.OWNER:
        raise is_owner()
    db.execute(
        delete(SecretOverride).where(
            SecretOverride.user_id == membership.user_id,
            SecretOverride.secret_id.in_(
                select(Secret.id).where(Secret.org_id == membership.org_id)
            ),
        )
    )
    db.delete(membership)


def transfer_ownership(db: DbSession, owner: Membership, user_id: UUID) -> None:
    """Hand the Organization to somebody else in it, and stay on as an admin.

    The old owner keeps a place, because the person who built an Organization
    losing access to it in the act of handing it on would be a surprise nobody
    asked for — and they may leave afterwards, which they could not before.

    Both rows are locked before either is written, so that two transfers of one
    Organization cannot both read one owner and leave two: the second waits,
    then finds the caller is no longer the owner and is refused.
    """
    held = locked(db, owner.org_id, owner.user_id)
    if held is None or held.role is not Role.OWNER:
        raise not_the_owner()
    if user_id == held.user_id:
        # Handing it to yourself is what already happened; the alternative
        # would be writing owner and admin onto the one row.
        return
    taking = locked(db, owner.org_id, user_id)
    if taking is None:
        raise unknown_member()
    taking.role = Role.OWNER
    held.role = Role.ADMIN


def locked(db: DbSession, org_id: UUID, user_id: UUID) -> Membership | None:
    """A Membership held against other writers until this request commits.

    `populate_existing` because the row is already in this session's identity
    map: without it the lock would be taken and the stale attributes kept, and
    the re-read would prove nothing.
    """
    return db.execute(
        select(Membership)
        .where(Membership.org_id == org_id, Membership.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def unknown_member() -> ApiError:
    """The one answer for a user id that is nobody in this Organization."""
    return ApiError(404, "member_not_found", "no such member of this Organization")


def is_owner() -> ApiError:
    """The refusal that keeps an Organization's one owner: theirs is the
    Membership nobody removes, demotes, or leaves out of."""
    return ApiError(403, "is_owner", "that Membership is the Organization's owner's")
