from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api.accounts.models import Membership, Role, User
from step_by_step_api.accounts.orgs import not_an_admin, not_the_owner
from step_by_step_api.errors import ApiError
from step_by_step_api.secrets.models import Secret, SecretOverride


def listing(db: DbSession, org_id: UUID) -> list[tuple[Membership, User]]:
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id)
        .order_by(Membership.created_at, User.email)
    ).all()
    return [(membership, user) for membership, user in rows]


def member(db: DbSession, org_id: UUID, user_id: UUID) -> Membership:
    membership = db.execute(
        select(Membership).where(
            Membership.org_id == org_id, Membership.user_id == user_id
        )
    ).scalar_one_or_none()
    if membership is None:
        raise unknown_member()
    return membership


def set_role(db: DbSession, org_id: UUID, user_id: UUID, role: Role) -> Membership:
    membership = member(db, org_id, user_id)
    if membership.role is Role.OWNER:
        raise is_owner()
    membership.role = role
    return membership


def remove(db: DbSession, caller: Membership, user_id: UUID) -> None:
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
    held = locked(db, owner.org_id, owner.user_id)
    if held is None or held.role is not Role.OWNER:
        raise not_the_owner()
    if user_id == held.user_id:
        return
    taking = locked(db, owner.org_id, user_id)
    if taking is None:
        raise unknown_member()
    taking.role = Role.OWNER
    held.role = Role.ADMIN


def locked(db: DbSession, org_id: UUID, user_id: UUID) -> Membership | None:
    return db.execute(
        select(Membership)
        .where(Membership.org_id == org_id, Membership.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def unknown_member() -> ApiError:
    return ApiError(404, "member_not_found", "no such member of this Organization")


def is_owner() -> ApiError:
    return ApiError(403, "is_owner", "that Membership is the Organization's owner's")
