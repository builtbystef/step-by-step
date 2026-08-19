"""Leaving, at both levels — and it is complete.

An owner ends an Organization; a user ends their own account. Both are hard
deletes with no grace period (ADR 0005), and both are behind typing what is
about to go: an irreversible act asks for a sentence nobody types by accident,
and the name and the address are the two things the person doing it already
knows.

What goes with each is the schema's, not this module's. Ownership cascades in
two directions and every table joins one of them: a table an Organization owns
references `organizations` with `ON DELETE CASCADE`, and the rows a user owns
— their sessions, their Memberships — reference `users` the same way. So one
`DELETE` takes everything that belonged to what it names, and no deletion can
leave a row pointing at something that is gone. `signin_codes` is the one
exception, because a Sign-in Code is keyed by an address rather than by an
account: it is deleted here, by hand.

The refusals are the two facts a screen has to say out loud. A mistyped
confirmation is 400 `confirmation_mismatch` and changes nothing. An account
that owns an Organization is 403 `sole_owner` — an Organization has exactly
one owner, so an owner leaving would leave a team with nobody who can rename
it, hand it on, or end it. Transferring ownership or ending the Organization
is the way out, and both are the person's own to do.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api.accounts.models import (
    Membership,
    Organization,
    Role,
    SigninCode,
    User,
)
from step_by_step_api.accounts.service import normalized
from step_by_step_api.errors import ApiError


def end_organization(db: DbSession, organization: Organization, typed: str) -> None:
    """End an Organization, with everything that belonged to it.

    The name is compared as it is stored, apart from the whitespace a paste
    carries: this is a confirmation rather than a password, and a trailing
    space is not a different intention. The case is not forgiven, because
    reading the name off the screen is the whole of the act.
    """
    if typed.strip() != organization.name:
        raise mismatch("that is not this Organization's name")
    db.delete(organization)


def end_account(db: DbSession, user: User, typed: str) -> None:
    """End an account: its sessions, its Memberships, and the user row.

    The address is compared without case, like every other comparison of an
    address here — the identity is the mailbox, and somebody who signed up as
    `Ada@Example.com` and types their address in lowercase has typed their
    address.

    Refused while the account owns an Organization. An Organization has
    exactly one owner, so an owner leaving would leave a team nobody can
    rename, hand on, or end; the way out is the transfer or the deletion, and
    both are this person's own to do.

    The confirmation is read first, so that the refusal about what this
    account still owns only ever reaches somebody who meant to end it.

    The Sign-in Code goes by hand because it is keyed by the address rather
    than by the account — it is the one row belonging to a user that no
    cascade reaches. The issuance count stays: it is what one address has been
    sent, and an account deletion that cleared it would be a way to ask for
    another five codes.
    """
    if normalized(typed) != normalized(user.email):
        raise mismatch("that is not this account's address")
    if owned_organizations(db, user):
        raise ApiError(
            403,
            "sole_owner",
            "you own an Organization; hand it on or end it first",
        )
    db.execute(delete(SigninCode).where(SigninCode.email == normalized(user.email)))
    db.delete(user)


def owned_organizations(db: DbSession, user: User) -> list[Organization]:
    """The Organizations this account is the owner of, if it owns any."""
    return list(
        db.execute(
            select(Organization)
            .join(Membership, Membership.org_id == Organization.id)
            .where(Membership.user_id == user.id, Membership.role == Role.OWNER)
            .order_by(Organization.created_at)
        )
        .scalars()
        .all()
    )


def mismatch(message: str) -> ApiError:
    """The refusal on a confirmation that does not match what it confirms."""
    return ApiError(400, "confirmation_mismatch", message)
