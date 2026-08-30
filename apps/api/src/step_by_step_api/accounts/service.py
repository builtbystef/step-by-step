from dataclasses import dataclass
from enum import StrEnum
from os import environ
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import mail
from step_by_step_api.accounts import codes, invitations, orgs
from step_by_step_api.accounts.models import Membership, Organization, Role, User
from step_by_step_api.errors import ApiError

SIGNUP_MODE_VARIABLE = "SIGNUP_MODE"

DEFAULT_TIMEZONE_VARIABLE = "DEFAULT_TIMEZONE"


class SignupMode(StrEnum):
    OPEN = "open"

    INVITE_ONLY = "invite_only"


class SignupModeError(RuntimeError):
    pass


def signup_mode() -> SignupMode:
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


class DefaultTimezoneError(RuntimeError):
    pass


def default_timezone() -> str:
    said = environ.get(DEFAULT_TIMEZONE_VARIABLE, "").strip()
    if not said:
        return "UTC"
    try:
        ZoneInfo(said)
    except (ZoneInfoNotFoundError, KeyError) as error:
        raise DefaultTimezoneError(
            f"{DEFAULT_TIMEZONE_VARIABLE}={said!r} is not an IANA timezone"
        ) from error
    return said


RATE_LIMITED = "rate_limited"

SIGNIN_SUBJECT = "Your Step by Step sign-in code"
SIGNUP_SUBJECT = "Your Step by Step sign-up code"


def normalized(email: str) -> str:
    return email.strip().lower()


def find_user(db: DbSession, email: str) -> User | None:
    return db.execute(
        select(User).where(func.lower(User.email) == normalized(email))
    ).scalar_one_or_none()


def may_sign_up(db: DbSession, address: str) -> bool:
    return signup_mode() is SignupMode.OPEN or bool(
        invitations.pending_for(db, address)
    )


def request_code(db: DbSession, email: str) -> None:
    address = normalized(email)
    if codes.count_issuance(db, address) > codes.ISSUANCE_LIMIT:
        raise ApiError(
            429,
            RATE_LIMITED,
            "too many codes have been requested for this address",
        )
    codes.sweep_closed_windows(db)
    code = codes.issue(db, address)
    signing_up = find_user(db, address) is None and may_sign_up(db, address)
    mail.send(
        to=email.strip(),
        subject=SIGNUP_SUBJECT if signing_up else SIGNIN_SUBJECT,
        text=code_email(code, signing_up),
    )


def code_email(code: str, signing_up: bool) -> str:
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


def create_account(db: DbSession, email: str, *, with_organization: bool) -> User:
    entered = email.strip()
    user = User(email=entered)
    db.add(user)
    db.flush()
    if with_organization:
        orgs.create(db, user, entered.split("@", 1)[0])
    return user


class Verdict(StrEnum):
    SIGNED_IN = "signed_in"

    BAD_CODE = "bad_code"

    CODE_EXHAUSTED = "code_exhausted"

    SIGNUP_CLOSED = "signup_closed"


@dataclass(frozen=True, slots=True)
class Verification:
    verdict: Verdict
    user: User | None = None
    created: bool = False


def verify_code(db: DbSession, email: str, code: str) -> Verification:
    address = normalized(email)
    attempt = codes.claim(db, address, code)
    if attempt is codes.Attempt.EXHAUSTED:
        return Verification(Verdict.CODE_EXHAUSTED)
    if attempt is not codes.Attempt.ACCEPTED:
        return Verification(Verdict.BAD_CODE)
    user = find_user(db, address)
    if user is not None:
        return Verification(Verdict.SIGNED_IN, user=user)
    if not may_sign_up(db, address):
        return Verification(Verdict.SIGNUP_CLOSED)
    opened = signup_mode() is SignupMode.OPEN
    return Verification(
        Verdict.SIGNED_IN,
        user=create_account(db, email, with_organization=opened),
        created=True,
    )


def refusal(verdict: Verdict) -> ApiError:
    if verdict is Verdict.SIGNUP_CLOSED:
        return ApiError(403, verdict, "this instance does not accept new accounts")
    if verdict is Verdict.CODE_EXHAUSTED:
        return ApiError(429, verdict, "that code has taken too many wrong guesses")
    return ApiError(401, verdict, "that code is not usable")


def organizations_of(db: DbSession, user: User) -> list[tuple[Organization, Role]]:
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at)
    ).all()
    return [(organization, role) for organization, role in rows]
