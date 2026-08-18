"""The accounts HTTP surface.

Every route here is under the one app origin, and every refusal is JSON with a
machine-readable code.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from step_by_step_api.accounts import service, sessions
from step_by_step_api.accounts.models import Role, User
from step_by_step_api.accounts.service import SignupMode, signup_mode
from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import errors

Email = Annotated[
    str, Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
]
"""An address, checked only for the shape every address has.

Whether it can receive mail is the mail server's answer, not a regular
expression's, and the flow already waits for that answer: an address that
cannot receive the Sign-in Code never signs in.
"""

router = APIRouter()


class Instance(BaseModel):
    """What an unauthenticated visitor may learn about this instance."""

    signup_mode: SignupMode


@router.get("/api/instance", operation_id="getInstance")
def get_instance() -> Instance:
    """The one fact the sign-in screen needs before anyone has signed in."""
    return Instance(signup_mode=signup_mode())


class CodeRequest(BaseModel):
    """Step one of the sign-in screen: the address to send a code to."""

    email: Email


@router.post(
    "/api/auth/request-code",
    operation_id="requestSigninCode",
    status_code=202,
    response_class=Response,
)
def request_signin_code(asked: CodeRequest, db: SessionDep) -> Response:
    """Mail a Sign-in Code to an address — 202 whether or not it is anybody.

    The answer must not vary with whether an account exists, or it becomes a
    way to ask which addresses are on this instance. So there is nothing in
    the body to differ, and the caller learns what happened by entering a code.
    """
    service.request_code(db, asked.email)
    db.commit()
    return Response(status_code=202)


class VerificationRequest(BaseModel):
    """Step two of the sign-in screen: the address, and the code it received."""

    email: Email
    code: str = Field(min_length=1, max_length=16)


class SignedIn(BaseModel):
    """What signing in tells the screen: whether this visit made the account.

    The screen needs it to decide between welcoming someone and letting them
    carry on, and it is the only thing that differs between the two.
    """

    created: bool


class OrganizationMembership(BaseModel):
    """One Organization a user acts in, and what they may do there."""

    id: UUID
    name: str
    role: Role


class Account(BaseModel):
    """Who the caller is. The email is theirs as they typed it."""

    id: UUID
    email: str
    display_name: str | None
    orgs: list[OrganizationMembership]


class AccountUpdate(BaseModel):
    """The one thing about an account its owner may change here."""

    display_name: str | None = Field(default=None, max_length=200)


def account_of(db: SessionDep, user: User) -> Account:
    """The account as every route that answers with one renders it."""
    return Account(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        orgs=[
            OrganizationMembership(id=org.id, name=org.name, role=role)
            for org, role in service.organizations_of(db, user)
        ],
    )


@router.post(
    "/api/auth/verify-code",
    operation_id="verifySigninCode",
    responses=errors(401, 403),
)
def verify_signin_code(
    asked: VerificationRequest, request: Request, response: Response, db: SessionDep
) -> SignedIn:
    """Prove control of an address, which signs in — and signs up if it is new."""
    verified = service.verify_code(db, asked.email, asked.code)
    if verified.user is None:
        # Committed before the refusal on purpose: a wrong guess counted
        # against the code, and a code spent on a closed instance, are both
        # facts that must survive the answer that carries them.
        db.commit()
        raise service.refusal(verified.verdict)
    sessions.carry(request, response, sessions.begin(db, verified.user))
    db.commit()
    return SignedIn(created=verified.created)


@router.get("/api/auth/me", operation_id="getCurrentAccount", responses=errors(401))
def get_current_account(user: CurrentUser, db: SessionDep) -> Account:
    """Who the caller is, and which Organizations they can act in."""
    return account_of(db, user)


@router.patch("/api/account", operation_id="updateAccount", responses=errors(401))
def update_account(change: AccountUpdate, user: CurrentUser, db: SessionDep) -> Account:
    """Change the display name. The email is the identity and is not editable."""
    user.display_name = change.display_name
    db.commit()
    return account_of(db, user)


@router.post(
    "/api/auth/logout",
    operation_id="signOut",
    status_code=204,
    response_class=Response,
    responses=errors(401),
)
def sign_out(request: Request, user: CurrentUser, db: SessionDep) -> Response:
    """End this session — the row goes, and the browser stops carrying its key.

    Other sessions of the same user are untouched; ending all of them is the
    session-expiry slice's `logout-all`.
    """
    token = request.cookies.get(sessions.SESSION_COOKIE, "")
    sessions.end(db, token)
    db.commit()
    answer = Response(status_code=204)
    sessions.drop(answer)
    return answer
