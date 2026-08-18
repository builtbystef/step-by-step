"""Signing up and signing in, which are one flow.

A visitor gives an address; a Sign-in Code goes to it; entering the code
proves they control it. That proof is the whole of authentication here (ADR
0005) — for someone who already has an account and for someone who does not,
which is why there is no separate sign-up.

There is no instance settings table and no instance administrator: one
environment variable decides whether an unknown address may become an account,
and the sign-in screen reads it from `/api/instance` rather than guessing.
"""

from dataclasses import dataclass
from enum import StrEnum
from os import environ

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import mail
from step_by_step_api.accounts import codes
from step_by_step_api.accounts.models import Membership, Organization, Role, User
from step_by_step_api.errors import ApiError

SIGNUP_MODE_VARIABLE = "SIGNUP_MODE"
"""Whether verifying a code for an unknown address creates an account."""


class SignupMode(StrEnum):
    OPEN = "open"
    """Anyone who controls an email address can make an account."""

    INVITE_ONLY = "invite_only"
    """Only an invited address can; everyone else meets `signup_closed`."""


class SignupModeError(RuntimeError):
    """`SIGNUP_MODE` says something that is not a mode."""


def signup_mode() -> SignupMode:
    """The instance's signup mode, `open` unless the environment says otherwise.

    Read per call rather than cached: it is one dictionary lookup, and caching
    it would make an operator's change need a restart for no gain. The hyphen
    of the spec's prose spelling is accepted, because a self-hoster who copies
    `invite-only` out of the documentation should get an invite-only instance
    rather than a boot failure.
    """
    said = environ.get(SIGNUP_MODE_VARIABLE, "").strip().lower().replace("-", "_")
    if not said:
        return SignupMode.OPEN
    try:
        return SignupMode(said)
    except ValueError:
        raise SignupModeError(
            f"{SIGNUP_MODE_VARIABLE}={said!r} is not a signup mode; "
            f"it is one of {SignupMode.OPEN}, {SignupMode.INVITE_ONLY}"
        ) from None


SIGNIN_SUBJECT = "Your Step by Step sign-in code"
SIGNUP_SUBJECT = "Your Step by Step sign-up code"


def normalized(email: str) -> str:
    """The form an address is compared and looked up by.

    Identity is case-insensitive, so the comparison key is lowercase — but a
    `users` row keeps the address as its owner typed it, and this value never
    replaces it.
    """
    return email.strip().lower()


def find_user(db: DbSession, email: str) -> User | None:
    """The account for an address, whatever case either side was written in."""
    return db.execute(
        select(User).where(func.lower(User.email) == normalized(email))
    ).scalar_one_or_none()


def request_code(db: DbSession, email: str) -> None:
    """Issue a Sign-in Code for an address and mail it.

    The caller answers 202 whether or not the address is anybody, so this must
    behave the same either way; only the wording of the email differs, and it
    differs by what entering the code will do rather than by what exists. An
    unknown address on an invite-only instance is therefore told nothing about
    invitations — it gets the sign-in wording, and the refusal it will meet is
    `signup_closed` at verification.
    """
    address = normalized(email)
    code = codes.issue(db, address)
    signing_up = find_user(db, address) is None and signup_mode() is SignupMode.OPEN
    mail.send(
        to=email.strip(),
        subject=SIGNUP_SUBJECT if signing_up else SIGNIN_SUBJECT,
        text=code_email(code, signing_up),
    )


def code_email(code: str, signing_up: bool) -> str:
    """The body of the one email every visitor of this instance receives."""
    opening = (
        "Enter this code to create your Step by Step account:"
        if signing_up
        else "Enter this code to sign in to Step by Step:"
    )
    return (
        f"{opening}\n\n"
        f"    {code}\n\n"
        "It works once, and it expires in 10 minutes.\n"
        "If you did not ask for it, nothing has happened and you can ignore "
        "this email."
    )


def create_account(db: DbSession, email: str) -> User:
    """The account, and the Organization it starts with.

    Signing up auto-creates an Organization owned by the new user, named after
    the address's local part (ADR 0005), so that a first workflow has a tenant
    to belong to before anyone has thought about tenancy. It is renameable, and
    it is the reason every user who signs up has at least one Membership.
    """
    entered = email.strip()
    user = User(email=entered)
    organization = Organization(name=entered.split("@", 1)[0])
    db.add_all([user, organization])
    db.flush()
    db.add(Membership(org_id=organization.id, user_id=user.id, role=Role.OWNER))
    return user


class Verdict(StrEnum):
    """How a verification came out. The refusals are the codes clients read."""

    SIGNED_IN = "signed_in"

    BAD_CODE = "bad_code"
    """Wrong, expired, already spent, or never issued — one answer for all
    four, because telling them apart would tell a guesser how close they are."""

    SIGNUP_CLOSED = "signup_closed"
    """The code was right, and this instance does not take new accounts."""


@dataclass(frozen=True, slots=True)
class Verification:
    """What verifying a code did, for the route to answer with."""

    verdict: Verdict
    user: User | None = None
    created: bool = False


def verify_code(db: DbSession, email: str, code: str) -> Verification:
    """Spend a Sign-in Code, and sign in — creating the account if it is new.

    Whatever this returns, the caller commits: a spent code, a counted wrong
    guess, and a created account are all things that must survive the answer.
    """
    address = normalized(email)
    if not codes.claim(db, address, code):
        return Verification(Verdict.BAD_CODE)
    user = find_user(db, address)
    if user is not None:
        return Verification(Verdict.SIGNED_IN, user=user)
    if signup_mode() is SignupMode.INVITE_ONLY:
        # The invited path — a pending Invitation as the signup permit — is
        # the Invitations slice's; until it lands, invite-only takes nobody new.
        return Verification(Verdict.SIGNUP_CLOSED)
    return Verification(Verdict.SIGNED_IN, user=create_account(db, email), created=True)


def refusal(verdict: Verdict) -> ApiError:
    """The refusal a verdict other than `signed_in` becomes on the wire."""
    if verdict is Verdict.SIGNUP_CLOSED:
        return ApiError(403, verdict, "this instance does not accept new accounts")
    return ApiError(401, verdict, "that code is not usable")


def organizations_of(db: DbSession, user: User) -> list[tuple[Organization, Role]]:
    """The Organizations a user acts in, with the role each Membership carries."""
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at)
    ).all()
    return [(organization, role) for organization, role in rows]
